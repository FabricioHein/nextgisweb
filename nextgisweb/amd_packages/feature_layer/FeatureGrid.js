/* globals ngwConfig */
define([
    "dojo/_base/declare",
    "dijit/layout/BorderContainer",
    "dijit/_TemplatedMixin",
    "dijit/_WidgetsInTemplateMixin",
    "dojo/text!./templates/FeatureGrid.html",
    // dgrid & plugins
    "dgrid/OnDemandGrid",
    "dgrid/Selection",
    "dgrid/extensions/ColumnHider",
    // other
    "dojo/_base/lang",
    "dojo/_base/array",
    "dojo/request/xhr",
    "dojo/Deferred",
    "dojo/promise/all",
    "dojo/store/Observable",
    "dojo/dom-style",
    // ngw
    "ngw/route",
    "./FeatureStore",
    // css
    "xstyle/css!" + ngwConfig.amdUrl + "dgrid/css/skins/claro.css",
    // template
    "dijit/layout/ContentPane",
    "dijit/Toolbar",
    "dijit/form/Button",
    "dijit/form/TextBox"
], function (
    declare,
    BorderContainer,
    _TemplatedMixin,
    _WidgetsInTemplateMixin,
    template,
    // dgrid & plugins
    OnDemandGrid,
    Selection,
    ColumnHider,
    // other
    lang,
    array,
    xhr,
    Deferred,
    all,
    Observable,
    domStyle,
    // ngw
    route,
    FeatureStore
) {
    // Базовый класс ggrid над которым затем делается обертка в dijit виджет
    var GridClass = declare([OnDemandGrid, Selection, ColumnHider], {
        selectionMode: "single"
    });

    return declare([BorderContainer, _TemplatedMixin, _WidgetsInTemplateMixin], {
        templateString: template,

        // Текущая веделенная строка
        selectedRow: null,

        // Показывать ли тулбар
        showToolbar: true,

        // Показывать ли строку поиска
        likeSearch: true,

        constructor: function (params) {
            declare.safeMixin(this, params);

            this._gridInitialized = new Deferred();

            var widget = this;

            xhr.get(route("feature_layer.field", {id: this.layerId}), {
                handleAs: "json"
            }).then(
                function (data) {
                    widget._fields = data;
                    widget.initializeGrid();
                }
            ).otherwise(console.error);

        },

        postCreate: function () {
            if (!this.showToolbar) {
                domStyle.set(this.toolbar.domNode, "display", "none");
            };

            this.watch("selectedRow", lang.hitch(this, function (attr, oldVal, newVal) {
                this.btnOpenFeature.set("disabled", newVal == null);
            }));

            this.btnOpenFeature.on("click", lang.hitch(this, this.openFeature));

            if (this.likeSearch) {
                // Поиск нужен, настраиваем обработчики строки поиска
                this.tbSearch.on("input", lang.hitch(this, function () {
                    if (this._timer != undefined) { clearInterval(this._timer) };
                    this._timer = setInterval(lang.hitch(this, this.updateSearch), 750);
                }));

                this.tbSearch.watch("value", lang.hitch(this, function(attr, oldVal, newVal) {
                    this.updateSearch();
                }));
            } else {
                // Поиск не нужен, прячем строку поиска
                domStyle.set(this.tbSearch.domNode, "display", "none");                
            };
        },

        initializeGrid: function () {
            var columns = [{
                field: "id",
                label: "#",
                unhidable: true
            }];

            var fields = [];

            array.forEach(this._fields, function (f) {
                columns.push({
                    field: "F:" + f.keyname,
                    label: f.display_name,
                    hidden: !f.grid_visibility
                });
                fields.push(f.keyname);
            });

            if (this.data == undefined) {
                this.store = new Observable(new FeatureStore({
                    layer: this.layerId,
                    fieldList: fields,
                    fieldPrefix: "F:"
                }));
            };

            this._grid = new GridClass({
                store: this.store ? this.store : undefined,
                columns: columns,
                queryOptions: this.queryOptions
            });

            if (this.data) {
                this._grid.renderArray(this.data);
            }

            domStyle.set(this._grid.domNode, "height", "100%");
            domStyle.set(this._grid.domNode, "border", "none");

            var widget = this;
            this._grid.on("dgrid-select", function (event) {
                widget.set("selectedRow", event.rows[0].data);
            });

            this._grid.on("dgrid-deselect", function () {
                widget.set("selectedRow", null);
            });

            this._gridInitialized.resolve();
        },

        startup: function () {
            this.inherited(arguments);

            var widget = this;
            this._gridInitialized.then(
                function () {
                    widget.gridPane.set("content", widget._grid.domNode);
                    widget._grid.startup();
                }
            );
        },

        openFeature: function() {
            window.open(route("feature_layer.feature.show", {
                id: this.layerId,
                feature_id: this.get("selectedRow").id
            }));
        },

        updateSearch: function () {
            if (this._timer != undefined) { clearInterval(this._timer) };

            var value = this.tbSearch.get("value");
            if (this._search != value) {
                this._search = value;
                this._grid.set("query", {like: this.tbSearch.get("value")});
            };
        }

    })
});