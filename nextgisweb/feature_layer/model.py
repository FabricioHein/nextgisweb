# -*- coding: utf-8 -*-
from collections import OrderedDict
from shutil import copyfileobj

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.orderinglist import ordering_list
from zope.interface import implements

from .. import db
from ..env import env
from ..models import declarative_base
from ..resource import (
    Resource,
    ResourceScope,
    DataScope,
    DataStructureScope,
    Serializer,
    SerializedProperty as SP)
from ..resource.exception import ValidationError
from ..file_storage import FileObj

from .interface import (
    FIELD_TYPE,
    IFeatureLayer,
    IFeatureLayerStyle)
from .util import _

Base = declarative_base()


class LayerField(Base):
    __tablename__ = 'layer_field'

    id = db.Column(db.Integer, primary_key=True)
    layer_id = db.Column(db.ForeignKey(Resource.id), nullable=False)
    cls = db.Column(db.Unicode, nullable=False)

    idx = db.Column(db.Integer, nullable=False)
    keyname = db.Column(db.Unicode, nullable=False)
    datatype = db.Column(db.Enum(*FIELD_TYPE.enum), nullable=False)
    display_name = db.Column(db.Unicode, nullable=False)
    grid_visibility = db.Column(db.Boolean, nullable=False, default=True)

    identity = __tablename__

    __mapper_args__ = {
        'polymorphic_identity': identity,
        'polymorphic_on': cls
    }

    layer = db.relationship(
        Resource,
        primaryjoin='Resource.id == LayerField.layer_id',
    )

    def __unicode__(self):
        return self.display_name

    def to_dict(self):
        return dict(
            (c, getattr(self, c))
            for c in (
                'id', 'layer_id', 'cls',
                'idx', 'keyname', 'datatype',
                'display_name', 'grid_visibility',
            )
        )


class LayerFieldsMixin(object):
    __field_class__ = LayerField
    __scope__ = DataStructureScope

    @declared_attr
    def fields(cls):
        return db.relationship(
            cls.__field_class__,
            foreign_keys=cls.__field_class__.layer_id,
            order_by=cls.__field_class__.idx,
            collection_class=ordering_list('idx'),
            cascade='all, delete-orphan',
            single_parent=True
        )

    @declared_attr
    def feature_label_field_id(cls):
        return db.Column(
            "feature_label_field_id",
            db.ForeignKey(cls.__field_class__.id)
        )

    @declared_attr
    def feature_label_field(cls):
        return db.relationship(
            cls.__field_class__,
            uselist=False,
            primaryjoin="%s.id == %s.feature_label_field_id" % (
                cls.__field_class__.__name__, cls.__name__
            ),
            cascade='all',
            post_update=True
        )


class _fields_attr(SP):

    def getter(self, srlzr):
        return map(
            lambda f: OrderedDict((
                ('id', f.id), ('keyname', f.keyname),
                ('datatype', f.datatype), ('typemod', None),
                ('display_name', f.display_name),
                ('label_field', f == srlzr.obj.feature_label_field),
                ('grid_visibility', f.grid_visibility))),
            srlzr.obj.fields)

    def setter(self, srlzr, value):
        obj = srlzr.obj

        fldmap = dict()
        for idx, fld in reversed(list(enumerate(list(obj.fields)))):
            if fld.id:
                fldmap[fld.id] = fld
                obj.fields.pop(idx)

        obj.feature_label_field = None

        for fld in value:
            fldid = fld.get('id')

            if fldid:
                mfld = fldmap.get(fldid)
                if mfld is None:
                    raise ValidationError(_("Field not found (ID=%d)." % fldid))
            else:
                mfld = obj.__field_class__(
                    datatype=fld['datatype'])

            if 'keyname' in fld:
                mfld.keyname = fld['keyname']
            if 'display_name' in fld:
                mfld.display_name = fld['display_name']
            if 'grid_visibility' in fld:
                mfld.grid_visibility = fld['grid_visibility']

            if fld.get('label_field', False):
                obj.feature_label_field = mfld

            obj.fields.append(mfld)

        obj.fields.reorder()


P_DSS_READ = DataStructureScope.read
P_DSS_WRITE = DataStructureScope.write


class FeatureLayerSerializer(Serializer):
    identity = 'feature_layer'
    resclass = LayerFieldsMixin

    fields = _fields_attr(read=P_DSS_READ, write=P_DSS_WRITE)


class FeatureLayerStyle(Base, Resource):
    identity = 'feature_layer_style'
    cls_display_name = _("Feature layer style")

    implements(IFeatureLayerStyle)

    __scope__ = DataScope

    fileobj_id = db.Column(db.ForeignKey(FileObj.id), nullable=True)
    fileobj = db.relationship(FileObj, cascade='all')

    @classmethod
    def check_parent(cls, parent):
        return IFeatureLayer.providedBy(parent)

    @property
    def srs(self):
        return self.parent.srs


class _file_upload_attr(SP):  # NOQA

    def setter(self, srlzr, value):
        srcfile, _ = env.file_upload.get_filename(value['id'])
        fileobj = env.file_storage.fileobj(component='feature_layer')
        srlzr.obj.fileobj = fileobj
        dstfile = env.file_storage.filename(fileobj, makedirs=True)

        with open(srcfile, 'r') as fs, open(dstfile, 'w') as fd:
            copyfileobj(fs, fd)


class FeatureLayerStyleSerializer(Serializer):
    identity = FeatureLayerStyle.identity
    resclass = FeatureLayerStyle

    file_upload = _file_upload_attr(read=None, write=ResourceScope.update)
