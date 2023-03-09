


function getGroupParam() {
  return window.location.href.slice(window.location.href.indexOf('?') + 1).split('searchStorageId=')[1];
}

$(document).ready(function() {
    $template = $(".template-storage-detail");
    var storage_ready=$('#storage').DataTable({
      "initComplete": function (settings, json) {
        let searchStorageId = getGroupParam()
        if (searchStorageId) {
          this.api().search(searchStorageId).draw()
        }
      },
      "ajax": {
        "url": "/api/v3/admin/storage/ready",
        "contentType": "application/json",
        "type": 'GET',
      },
      "sAjaxDataProp": "",
      "language": {
        "loadingRecords": '<i class="fa fa-spinner fa-pulse fa-3x fa-fw"></i><span class="sr-only">Loading...</span>'
      },
      "rowId": "id",
      "deferRender": true,
        "columns": [
            {
                "className":      'details-control',
                "orderable":      false,
                "data":           null,
                "width": "10px",
                "defaultContent": '<button class="btn btn-xs btn-info" type="button"  data-placement="top" ><i class="fa fa-plus"></i></button>'
            },
            { "data": "directory_path",},
            { "data": "id",},
            { "data": "type",},
            { "data": null},
            { "data": null},
            { "data": "parent",},
            { "data": "user_name",},
            { "data": "category",},
            { "data": "domains",},
            { "data": "status_logs",}
        ],
        "columnDefs": [
            {
                "targets": 4,
                "render": function ( data, type, full, meta ) {
                    if( full['status'] == 'ready' && 'qemu-img-info' in full){
                        return Math.round(full["qemu-img-info"]["virtual-size"]/1024/1024/1024)+" GB"
                    }else{
                        return '-'
                    }
                }},
                {
                "targets": 5,
                "render": function ( data, type, full, meta ) {
                    if( full['status'] == 'ready' && 'qemu-img-info' in full){
                        return Math.round(full["qemu-img-info"]["actual-size"]/1024/1024/1024)+' GB ('+Math.round(full["qemu-img-info"]["actual-size"]*100/full["qemu-img-info"]["virtual-size"])+'%)'
                    }else{
                        return '-'
                    }
                }},
                {
                  "targets": 9,
                  "render": function ( data, type, full, meta ) {
                      return full['domains'].length
                  }},
                {
                  "targets": 10,
                  "render": function ( data, type, full, meta ) {
                    if( "status_logs" in full ){
                      return moment.unix(full["status_logs"][full["status_logs"].length -1]["time"]).fromNow()
                    }
                    return "-"
                }
            }],
    });

    $('#storage tbody').on('click', 'td.details-control', function () {
        var tr = $(this).closest("tr");
        var row = storage_ready.row(tr);
        var rowData = row.data();

        if (row.child.isShown()) {
          // This row is already open - close it
          row.child.hide();
          tr.removeClass("shown");
        //   storage_ready.ajax.reload();

          // Destroy the Child Datatable
          $("#cl" + rowData.clientID)
            .DataTable()
            .destroy();
        } else {
            // Open this row
            row.child(format(rowData)).show();
            var id = rowData.id;

            childTable = $("#cl" + id).DataTable({
              dom: "t",
              ajax: {
                url: "/admin/storage/domains/" + id,
                contentType: "application/json",
                type: "GET",
              },
              sAjaxDataProp: "",
              language: {
                loadingRecords:
                  '<i class="fa fa-spinner fa-pulse fa-3x fa-fw"></i><span class="sr-only">Loading...</span>',
              },
              columns: [
                { data: "kind" },
                { data: "name" },
              ],
              columnDefs: [
              ],
              select: false,
            });

            tr.addClass("shown");
          }
    } );

    $('.btn-tree').on('click', function(){
      $('form').each(function() {
        this.reset();
      })

      $('#modalTreeDisk').modal({
        backdrop: 'static',
        keyboard: false
      }).modal('show');

      populateDiskTree();
    });

    var storage_deleted=$('#storage_deleted').DataTable( {
        "ajax": {
        "url": "/api/v3/admin/storage/deleted",
                "contentType": "application/json",
                "type": 'GET',
        },
        "sAjaxDataProp": "",
      "language": {
        "loadingRecords": '<i class="fa fa-spinner fa-pulse fa-3x fa-fw"></i><span class="sr-only">Loading...</span>'
      },
      "rowId": "id",
      "deferRender": true,
        "columns": [
            { "data": "id",},
            { "data": "type",},
            { "data": null},
            { "data": null},
            { "data": "user_name",},
            { "data": "category",},
            { "data": "status_logs"}
        ],
        "columnDefs": [
          {
            "targets": 2,
            "render": function ( data, type, full, meta ) {
                if( 'qemu-img-info' in full){
                    return Math.round(full["qemu-img-info"]["virtual-size"]/1024/1024/1024)+" GB"
                }else{
                    return '-'
                }
            }},
            {
            "targets": 3,
            "render": function ( data, type, full, meta ) {
                if( 'qemu-img-info' in full){
                    return Math.round(full["qemu-img-info"]["actual-size"]/1024/1024/1024)+' GB ('+Math.round(full["qemu-img-info"]["actual-size"]*100/full["qemu-img-info"]["virtual-size"])+'%)'
                }else{
                    return '-'
                }
            }},
          {
            "targets": 6,
            "render": function ( data, type, full, meta ) {
              return moment.unix(full["status_logs"][full["status_logs"].length -1]["time"]).fromNow()
          }
        }],
    });

    if( $("#storage_physical").length != 0){
      var storage_physical=$('#storage_physical').DataTable( {
        "ajax": {
        "url": "/api/v3/admin/storage/physical/domains",
                "contentType": "application/json",
                "type": 'GET',
        },
        "sAjaxDataProp": "",
        "language": {
          "loadingRecords": '<i class="fa fa-spinner fa-pulse fa-3x fa-fw"></i><span class="sr-only">Loading...</span>'
        },
        "rowId": "id",
        "deferRender": true,
          "columns": [
            { "data": ""},
            { "data": "path",},
            { "data": "correct-chain",},
            { "data": "size"},
            { "data": "hyper"},
            { "data": "domains"},
            { "data": "tomigrate"},
            {
              "className": 'text-center',
              "data": null,
              "orderable": false,
              "defaultContent": '<input type="checkbox" class="form-check-input"></input>'
            }
        ],
        "columnDefs": [
          {
            "targets": 3,
            "render": function ( data, type, full, meta ) {
              return Math.round(data/1000/1000/1000)+" GB"
            }
          },
          {
            "targets": 0,
            "render": function ( data, type, full, meta ) {
              return '<button type="button" id="btn-info" class="btn btn-pill-right btn-success btn-xs"><i class="fa fa-info"></i></button>';
            }
          }
        ],
      });

      $('#storage_physical tbody').on( 'click', 'button', function () {
        var data = storage_physical.row( $(this).parents('tr') ).data();
        switch($(this).attr('id')){
          case 'btn-info':
            $.ajax({
              type: "GET",
              url:
                "/api/v3/admin/storage/physical/toolbox_host",
              contentType: "application/json",
              success: function (toolbox_host) {
                $.ajax({
                  type: "POST",
                  url: toolbox_host+"/storage/disk/info",
                  headers: {"Authorization": "Bearer " +localStorage.getItem("token")},
                  data: JSON.stringify({
                    'path_id': data.path
                  }),
                  contentType: "application/json",
                  success: function (disk_info) {
                    new PNotify({
                      title: "Disk info.",
                        text: JSON.stringify(disk_info),
                        hide: true,
                        delay: 10000,
                        icon: 'fa fa-info',
                        opacity: 1,
                        type: 'info'
                    });
                  },
                });
              },
              error: function (xhr, ajaxOptions, thrownError) {
                if (xhr.status == 428) {
                  new PNotify({
                      title: "ERROR acessing storage",
                      text: xhr.responseJSON.description,
                      hide: true,
                      delay: 3000,
                      icon: 'fa fa-warning',
                      opacity: 1,
                      type: 'error'
                  });
                }
              }
            });
        break;
      }
      })

      storage_physical.on( 'click', 'tr[role="row"]', function (e) {
        toggleRow(this, e);
      });

      $(".btn-phy-update").on("click", function () {
        new PNotify({
          title: "重新扫描存储上的物理磁盘",
          text: "你真的要重新扫描所有这些吗？",
          hide: false,
          opacity: 0.9,
          confirm: { confirm: true },
          buttons: { closer: false, sticker: false },
          history: { history: false },
          addclass: "pnotify-center",
        })
          .get()
          .on("pnotify.confirm", function () {
            rescan_pnotify = new PNotify({
              title: "等待存储",
                text: "存储正在寻找存储中的文件。 请稍候，这可能需要几分钟...",
                hide: false,
                icon: 'fa fa-alert-sign',
                opacity: 1,
                type: "warning",
            });
            $.ajax({
              type: "GET",
              url:
                "/api/v3/admin/storage/physical/toolbox_host",
              contentType: "application/json",
              success: function (toolbox_host) {
                $.ajax({
                  type: "PUT",
                  url: toolbox_host+"/storage/disks",
                  contentType: "application/json",
                  success: function (data) {
                    storage_physical.ajax.reload();
                    rescan_pnotify.update({
                      title: "Physical storage",
                      text:  "更新 "+data.templates+" 模板和 "+data.desktops+" 桌面磁盘来自 "+toolbox_host,
                      hide: true,
                      delay: 5000,
                      opacity: 1,
                      type: 'success'
                  });
                  },
                });
              },
              error: function (xhr, ajaxOptions, thrownError) {
                console.log(xhr)
                if (xhr.status == 428) {
                  new PNotify({
                      title: "访问存储时出错",
                      text: xhr.responseJSON.description,
                      hide: true,
                      delay: 3000,
                      icon: 'fa fa-warning',
                      opacity: 1,
                      type: 'error'
                  });
                }
              }
            });
          })
          .on("pnotify.cancel", function () {});
      });

      $('#mactions').on('change', function () {
        action=$(this).val();
        names=''
        ids=[]

        if(storage_physical.rows('.active').data().length){
            $.each(storage_physical.rows('.active').data(),function(key, value){
                if(value["tomigrate"] == true){
                  names+=value['path']+'\n';
                  ids.push(value['path']);
                }
            });
            var text = "您即将\n- 激活维护模式\n- 在执行时停止所有桌面\n "+action+" 这些“迁移”物理磁盘：\n\n "+names
        }else{
            $.each(storage_physical.rows({filter: 'applied'}).data(),function(key, value){
              if(value["tomigrate"] == true){
                ids.push(value['path']);
              }
            });
            var text = "您即将\n- 激活维护模式\n- 在执行时停止所有桌面\n "+action+" "+ids.length+" 磁盘！\n 列表中的所有“要迁移”磁盘!"
        }

        new PNotify({
            title: '警告!',
              text: text,
              hide: false,
              opacity: 0.9,
              confirm: {
                confirm: true
              },
              buttons: {
                closer: false,
                sticker: false
              },
              history: {
                history: false
              },
              addclass: 'pnotify-center'
            }).get().on('pnotify.confirm', function() {
              new PNotify({
                title: "迁移磁盘.",
                  text: "激活维护模式并停止域",
                  hide: true,
                  delay: 4250,
                  icon: 'fa fa-alert',
                  opacity: 1,
                  type: 'warning',
              });
              $.ajax({
                type: "POST",
                url:"/api/v3/admin/storage/physical/multiple_actions/"+action,
                data: JSON.stringify({'paths':ids}),
                contentType: 'application/json',
                success: function(data)
                {
                  storage_physical.ajax.reload()
                },
                always: function(data)
                {
                  $('#mactions option[value="none"]').prop("selected", true);
                  $('#domains tr.active').removeClass('active')
                  $('#mactions option[value="none"]').prop("selected",true);
                }
              });
            } )
      })
    }
    $.getScript("/isard-admin/static/admin/js/socketio.js", socketio_on)
})
function socketio_on(){
    var storage_migration_progress = null
    socket.on('storage_migration_progress', function(data) {
        var data = JSON.parse(data);
        if (storage_migration_progress == null){
          storage_migration_progress = new PNotify({
            title: "迁移磁盘。 维护模式激活.",
              text: data.description+ "\nProgress: "+data.current+"/"+data.total,
              hide: false,
              icon: 'fa fa-'+data.type,
              opacity: 1,
              type: data.type,
          });
        }else{
          storage_migration_progress.update({
            title: "迁移磁盘。 维护模式激活.",
              text: data.description+ "\nProgress: "+data.current+"/"+data.total+"\nPLEASE WAIT!",
              hide: false,
              icon: 'fa fa-'+data.type,
              opacity: 1,
              type: data.type,
          });
        }
        if ("id" in data){
          storage_physical.row('#'+data.id).remove().draw();
        }

        if(data.current >= data.total){
          PNotify.removeAll()
          storage_ready.ajax.reload()}
    });
}

function format(rowData) {
    var childTable =
      '<table id="cl' +
      rowData.id +
      '" class="display compact nowrap w-100" width="100%">' +
      "</table>";
    return $(childTable).toArray();
}

function populateDiskTree(){
  $(":ui-fancytree").fancytree("destroy")
  $("#modalTreeDisk .storage_disk_tree").fancytree({
    extensions: ["table"],
    table: {
      indentation: 20,      // indent 20px per node level
      nodeColumnIdx: 1,     // render the node title into the 2nd column
    },
    source: {
      url: "/api/v3/admin/storage/tree_list",
      cache: false
    },
    lazyLoad: function(event, data){
      data.result = $.ajax({
        url: "/api/v3/admin/storage/tree_list",
        dataType: "json"
      });
    },
    renderColumns: function(event, data) {
      var node = data.node,
      $tdList = $(node.tr).find(">td");
      $tdList.eq(0).text(node.getIndexHier());
      // Fancy tree populates id column (1) as title
      $tdList.eq(2).text(node.data.user_name);
      if (node.data.directory_path == "/isard/templates") {
        $tdList.eq(3).text("Template");
      } else if (node.data.directory_path == "/isard/groups") {
        $tdList.eq(3).text("Desktop");
      }
      $tdList.eq(4).text(node.data.category_name);
    }
  });
}
