"use strict";angular.module("grapheneSemsApp",["ngCookies","ngResource","ngSanitize","ngRoute","sg.graphene","ui.bootstrap","ui.jq","stanleygu.spinners"]).config(["$routeProvider",function(a){a.when("/",{templateUrl:"views/main.html",controller:"MainCtrl"}).otherwise({redirectTo:"/"})}]),angular.module("grapheneSemsApp").controller("MainCtrl",["$scope","$http","$log",function(a,b,c){a.zoom=!0,a.width=720,a.height=700,a.charge=-1e3,a.gravity=0,a.linkDistance=5,a.renderFps=20;var d={focused:1,unfocused:.1,normal:1},e=function(a){console.log("Clicked on "+a.name)},f=function(a){console.log("Double clicked on "+a.name)},g=function(a,b){a.opacity=d.focused,_.each(b.imports.nodes,function(b){b.data.id!==a.data.id&&(b.opacity=d.unfocused)}),_.each(b.imports.edges,function(b){b.source.data.id!==a.data.id&&b.target.data.id!==a.data.id?b.opacity=d.unfocused:(b.opacity=d.focused,b.target.opacity=d.focused,b.source.opacity=d.focused)})},h=function(a,b){_.each(b.imports.nodes,function(a){a.opacity=d.normal}),_.each(b.imports.edges,function(a){a.opacity=d.normal})};a.events={click:e,dblClick:f,mouseover:g,mouseleave:h},a.dropzoneConfig={init:function(){this.on("addedfile",function(b){var c=new FileReader;c.onload=function(){a.data=angular.fromJson(c.result),a.$apply()},c.readAsText(b)})},url:"/",autoProcessQueue:!1,error:function(a,b,c){console.log("Error! ",c)}},b.get("sample.json").success(function(b){a.data=b});var i=function(a){return _.contains(a,"bives-modified")?"yellow":_.contains(a,"bives-inserted")?"green":_.contains(a,"bives-deleted")?"red":void 0},j=function(a){return _.contains(a,"bives-ioedge")?"arrow":_.contains(a,"bives-unkwnmod")?"diamond":_.contains(a,"bives-stimulator")?"emptyArrow":_.contains(a,"bives-inhibitor")?"flat":void 0};a.runLayout=function(){var b=[],c=[],d={},e={};_.each(a.data.elements.nodes,function(a){(_.contains(a.classes,"reaction")||_.contains(a.classes,"species"))&&(d[a.data.id]=a,e[a.data.id]={to:[],from:[]},b.push(a),_.contains(a.classes,"reaction")?(a.width=22,a.height=22):(a.width=60,a.height=20),a.color=i(a.classes))}),_.each(a.data.elements.edges,function(a){var b=d[a.data.source],f=d[a.data.target];b&&f&&(a.source=b,a.target=f,c.push(a),e[b.data.id].from.push(a),e[f.data.id].to.push(a),a.color=i(a.classes),a.marker=j(a.classes))}),a.force=d3.layout.force().charge(a.charge||-700).linkDistance(a.linkDistance||40).gravity(a.gravity||.1).size([a.width||800,a.height||800]);var f=_.throttle(function(){a.$digest()},1e3/a.renderFps);a.force.nodes(b).links(c).on("tick",function(){a.height&&a.width&&_.each(b,function(b){b.x=Math.max(b.width,Math.min(a.width-b.width,b.x)),b.y=Math.max(b.height,Math.min(a.height-b.height,b.y))}),f()}).on("end",function(){a.loading=!1,a.$digest()}).start(),a.loading=!0,a.exports={nodes:b,edges:c,force:a.force,nodeLookup:d,edgeLookup:e,zoom:a.zoom,events:a.events,allowUnstick:!0}},a.$watch("data",function(b){b&&a.runLayout()});var k=["charge","linkDistance","gravity"];_.each(k,function(b){a.$watch(b,function(d){d&&a.force&&(a.force[b](d).start())})})}]),angular.module("grapheneSemsApp").controller("LayoutCtrl",["$scope","sgGeo",function(a,b){a._=_,a.spacer=8,a.height=700,a.width=700,a.show={id:!0};var c=function(c){var d=b.getLineIntersectionWithRectangle({x1:c.source.x,y1:c.source.y,x2:c.target.x,y2:c.target.y},{x1:c.source.x-(c.source.width/2+a.spacer),y1:c.source.y-(c.source.height/2+a.spacer),x2:c.source.x+c.source.width/2+a.spacer,y2:c.source.y+c.source.height/2+a.spacer}),e=b.getLineIntersectionWithRectangle({x1:c.source.x,y1:c.source.y,x2:c.target.x,y2:c.target.y},{x1:c.target.x-(c.target.width/2+a.spacer),y1:c.target.y-(c.target.height/2+a.spacer),x2:c.target.x+c.target.width/2+a.spacer,y2:c.target.y+c.target.height/2+a.spacer});c.x1=d.x,c.y1=d.y,c.x2=e.x,c.y2=e.y};a.$watchCollection("imports.edges",function(b){b&&(a.links=a.imports.edges,_.each(a.links,function(b){a.$watch(function(){return b.source.x+b.source.y+b.target.x+b.target.y},function(){c(b)}),c(b)}))}),a.arrow=d3.svg.symbol().size(function(a){return a.size}).type(function(a){return a.type}),a.clickNode=function(b,c){var d=a.imports.events.click;_.isFunction(d)&&d(b,a,c)},a.dblClickNode=function(b,c){var d=a.imports.events.dblClick;_.isFunction(d)&&d(b,a,c)},a.mouseoverNode=function(b,c){var d=a.imports.events.mouseover;_.isFunction(d)&&d(b,a,c)},a.mouseleaveNode=function(b,c){var d=a.imports.events.mouseleave;_.isFunction(d)&&d(b,a,c)}}]);