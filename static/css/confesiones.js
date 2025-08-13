let offset = 0;
let isScrolling = false;

$(document).ready(function() {
    const modal = $("#modal");
    const btnNewConf = $("#btn-new-conf");
    const modalClose = $("#modal-close");
    const btnDescartar = $("#btn-descartar");
    const formConfesion = $("#form-confesion");
    const contenedorConfesiones = $("#contenedor-confesiones");
    const loadingMessage = $("#loading");

    // Modal
    btnNewConf.on("click", function() {
        modal.show();
    });

    modalClose.on("click", function() {
        modal.hide();
    });

    btnDescartar.on("click", function() {
        formConfesion[0].reset();
        modal.hide();
    });

    $(window).on("click", function(event) {
        if ($(event.target).is(modal)) {
            modal.hide();
        }
    });

    // Enviar confesión con AJAX
    formConfesion.on("submit", function(e) {
        e.preventDefault();
        let formData = new FormData(this);
        $.ajax({
            url: $(this).attr("action"),
            type: "POST",
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                if (response.success) {
                    contenedorConfesiones.prepend(response.html);
                    formConfesion[0].reset();
                    modal.hide();
                } else {
                    alert(response.message);
                }
            },
            error: function() {
                alert("Ocurrió un error al publicar la confesión.");
            }
        });
    });

    // Reacciones
    window.reaccionar = function(id, tipo) {
        $.ajax({
            url: `/reaccion_conf/${id}/${tipo}`,
            type: "POST",
            success: function(response) {
                if (response.success) {
                    let btn = $(`#conf-${id} .emoji-btn:contains('${tipo}')`);
                    let span = btn.find("span");
                    let count = parseInt(span.text()) + 1;
                    span.text(count);
                }
            }
        });
    };

    // Comentarios
    window.comentar = function(id) {
        let input = $(`#input-comentario-${id}`);
        let texto = input.val().trim();
        if (texto === "") return;
        $.ajax({
            url: `/comentar_conf`,
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ id: id, texto: texto }),
            success: function(response) {
                if (response.success) {
                    let comentariosLista = $(`#comentarios-${id}`);
                    let nuevoComentario = `
                        <div class="comentario-item">
                            <span class="comentario-usuario">${response.comentario.usuario}:</span>
                            <span class="comentario-texto">${response.comentario.texto}</span>
                        </div>
                    `;
                    comentariosLista.append(nuevoComentario);
                    input.val("");
                }
            }
        });
    };

    // Eliminar confesión
    window.eliminarConfesion = function(id) {
        if (confirm("¿Estás seguro de que quieres eliminar esta confesión?")) {
            $.ajax({
                url: `/eliminar_conf/${id}`,
                type: "POST",
                success: function(response) {
                    if (response.success) {
                        $(`#conf-${id}`).fadeOut(500, function() {
                            $(this).remove();
                        });
                    } else {
                        alert(response.message);
                    }
                },
                error: function() {
                    alert("No tienes permiso para eliminar esta confesión.");
                }
            });
        }
    };

    // Filtros
    window.cargarFiltro = function(tipo) {
        offset = 0;
        contenedorConfesiones.empty();
        loadingMessage.show();
        $.get(`/confesiones/filtro/${tipo}`, function(data) {
            contenedorConfesiones.html(data.html);
            loadingMessage.hide();
        }).fail(function() {
            loadingMessage.hide();
            alert("Error al cargar las confesiones.");
        });
    };

    // Carga infinita
    function cargarMasConfesiones() {
        if (isScrolling) return;
        isScrolling = true;
        loadingMessage.show();
        $.get("/confesiones_scroll", { offset: offset }, function(data) {
            contenedorConfesiones.append(data.html);
            offset += data.count;
            isScrolling = false;
            loadingMessage.hide();
        });
    }

    $(window).scroll(function() {
        if ($(window).scrollTop() + $(window).height() >= $(document).height() - 100) {
            cargarMasConfesiones();
        }
    });

    // Cargar las confesiones iniciales (si no hay ninguna al cargar la página)
    if (contenedorConfesiones.children().length === 0) {
        cargarMasConfesiones();
    }
});