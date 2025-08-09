let offset = 0;
let cargando = false;

// Funciones globales accesibles desde el HTML
window.cargarFiltro = function(tipo) {
    if (cargando) return;
    cargando = true;
    $('#loading').show();
    $.get(`/confesiones/filtro/${tipo}`, function(data) {
        if (data.html) {
            $('#contenedor-confesiones').html(data.html);
            offset = $(data.html).filter('.confesion-card').length;
        }
        $('#loading').hide();
        cargando = false;
    });
};

window.alternarModo = function() {
    $('body').toggleClass("modo-claro");
    if ($('body').hasClass("modo-claro")) {
        localStorage.setItem("modo", "claro");
    } else {
        localStorage.removeItem("modo");
    }
};

window.reaccionar = function(conf_id, tipo) {
    $.post(`/reaccion_conf/${conf_id}/${tipo}`, function(data) {
        if (data.success) {
            let selector = `#reaccion-${conf_id}-${tipo}`;
            let count = parseInt($(selector).text());
            $(selector).text(count + 1);
        }
    });
};

window.comentar = function(conf_id) {
    let input = $(`#comentario-${conf_id}`);
    let texto = input.val().trim();
    if (!texto) return;

    $.ajax({
        url: '/comentar_conf',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ id: conf_id, texto: texto }),
        success: function(data) {
            if (data.success) {
                $(`#comentarios-${conf_id}`).append(`<p><b>${data.comentario.usuario}:</b> ${data.comentario.texto}</p>`);
                input.val('');
            }
        }
    });
};

window.eliminarConfesion = function(conf_id) {
    if (!confirm('¿Estás seguro de que quieres eliminar esta confesión?')) return;
    $.post(`/eliminar_conf/${conf_id}`, function(data) {
        if (data.success) {
            $(`#conf-${conf_id}`).fadeOut(300, () => $(`#conf-${conf_id}`).remove());
        } else {
            alert(data.message);
        }
    });
};

// Lógica principal de jQuery que se ejecuta cuando la página está lista
$(document).ready(function() {
    // Inicializa el offset con el número de confesiones cargadas inicialmente
    offset = $('#contenedor-confesiones .confesion-card').length;
    
    // Si el modo claro estaba guardado, lo aplica
    if (localStorage.getItem("modo") === "claro") {
        $('body').addClass("modo-claro");
    }

    // Abrir modal con botón flotante
    $('#btn-new-conf').on('click', () => $('#modal').fadeIn());

    // Cerrar modal con la cruz o botón Descartar
    $('#modal-close, #btn-descartar').on('click', () => {
        $('#modal').fadeOut();
        $('#form-confesion')[0].reset();
    });

    // Enviar formulario de confesión vía AJAX
    $('#form-confesion').on('submit', function(e) {
        e.preventDefault();
        let formData = new FormData(this);
        $.ajax({
            url: $(this).attr('action'),
            method: 'POST',
            data: formData,
            contentType: false,
            processData: false,
            headers: {'X-Requested-With': 'XMLHttpRequest'},
            success: function(res) {
                if (res.success && res.html) {
                    $('#contenedor-confesiones').prepend(res.html);
                    $('#modal').fadeOut();
                    $('#form-confesion')[0].reset();
                    offset++;
                } else {
                    alert(res.message || 'No se pudo publicar la confesión.');
                }
            },
            error: function() {
                alert('Error en la conexión.');
            }
        });
    });

    // Delegación de eventos para botones en tarjetas
    $('#contenedor-confesiones').on('click', '.emoji-btn', function() {
        let conf_id = $(this).closest('.confesion-card').attr('id').replace('conf-', '');
        let tipo = $(this).data('tipo');
        reaccionar(conf_id, tipo);
    });

    $('#contenedor-confesiones').on('click', '.enviar-btn', function() {
        let conf_id = $(this).closest('.confesion-card').attr('id').replace('conf-', '');
        comentar(conf_id);
    });

    $('#contenedor-confesiones').on('click', '.eliminar-btn', function() {
        let conf_id = $(this).closest('.confesion-card').attr('id').replace('conf-', '');
        eliminarConfesion(conf_id);
    });
    
    // Scroll infinito para cargar más confesiones
    function cargarMasConfesiones() {
        if (cargando) return;
        cargando = true;
        $('#loading').show();
        $.get(`/confesiones_scroll?offset=${offset}`, function(data) {
            if (data.html) {
                $('#contenedor-confesiones').append(data.html);
                offset += $(data.html).filter('.confesion-card').length;
            }
            $('#loading').hide();
            cargando = false;
        });
    }

    $(window).on('scroll', () => {
        if (!cargando && $(window).scrollTop() + $(window).height() >= $(document).height() - 200) {
            cargarMasConfesiones();
        }
    });
});