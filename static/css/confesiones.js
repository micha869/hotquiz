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
    contenedorConfesiones.on("click", ".emoji-btn", function() {
        const btn = $(this);
        const confId = btn.closest(".confesion-card").attr("id").replace("conf-", "");
        const emojiTipo = btn.text().trim().split(" ")[0];
        $.ajax({
            url: `/reaccion_conf/${confId}/${emojiTipo}`,
            type: "POST",
            success: function(response) {
                if (response.success) {
                    let span = btn.find("span");
                    let count = parseInt(span.text()) + 1;
                    span.text(count);
                }
            },
            error: function() {
                alert("Ocurrió un error al reaccionar.");
            }
        });
    });

    // Comentarios (fix click en SVG + null check)
    contenedorConfesiones.on("click", ".enviar-btn, .enviar-btn *", function(e) {
        e.preventDefault();
        const btn = $(this).closest(".enviar-btn");
        const card = btn.closest(".confesion-card");
        const input = card.find(".comentario-input");

        if (input.length === 0) {
            console.error("No se encontró el campo de comentario.");
            return;
        }

        const texto = (input.val() || "").trim();
        if (!texto) return;

        $.ajax({
            url: `/comentar_conf`,
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ id: card.attr("id").replace("conf-", ""), texto: texto }),
            success: function(response) {
                if (response.success) {
                    card.find(".comentarios-lista").append(`
                        <div class="comentario-item">
                            <span class="comentario-usuario">${response.comentario.usuario}:</span>
                            <span class="comentario-texto">${response.comentario.texto}</span>
                        </div>
                    `);
                    input.val("");
                } else {
                    alert(response.message || "Error al comentar.");
                }
            },
            error: function() {
                alert("Ocurrió un error al comentar.");
            }
        });
    });

    // Eliminar confesión
    contenedorConfesiones.on("click", ".delete-btn", function() {
        const confId = $(this).closest(".confesion-card").attr("id").replace("conf-", "");
        if (confirm("¿Estás seguro de que quieres eliminar esta confesión?")) {
            $.ajax({
                url: `/eliminar_conf/${confId}`,
                type: "POST",
                success: function(response) {
                    if (response.success) {
                        $(`#conf-${confId}`).fadeOut(500, function() {
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
    });

    // Filtros
    $(".filters").on("click", ".btn-filter", function() {
        const tipo = $(this).text().trim().split(" ")[1].toLowerCase();
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
    });

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

    // Cargar las confesiones iniciales si no hay ninguna
    if (contenedorConfesiones.children().length === 0) {
        cargarMasConfesiones();
    }
});
