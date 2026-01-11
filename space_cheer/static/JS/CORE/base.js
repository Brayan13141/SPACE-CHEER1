document.addEventListener('DOMContentLoaded', function () {
    // Auto-dismiss after 5 seconds
    const messages = document.querySelectorAll('.alert-message');

    messages.forEach((message) => {
        // Verifica que la librería de Bootstrap esté disponible
        if (typeof bootstrap === 'undefined' || !bootstrap.Alert) {
            console.error(
                "Bootstrap's JavaScript is not loaded or Alert component is missing."
            );
            return;
        }

        // El mensaje tiene la clase 'show' por defecto
        setTimeout(() => {
            // 1. Instanciar el objeto Alert de Bootstrap, pasando el elemento DOM (message)
            const bsAlert = new bootstrap.Alert(message);

            // 2. Usar el método .close() o .dispose() para activarlo.
            // .close() activa el evento 'close.bs.alert' y el efecto fade.
            bsAlert.close();

            // Nota: El proceso de fade out toma tiempo (generalmente 500ms).
            // Si el mensaje necesita ser completamente eliminado del DOM inmediatamente,
            // .dispose() es una opción si no te importa el efecto fade,
            // pero .close() es lo que quieres aquí para el efecto "dismissible".
        }, 5000); // 5000 milisegundos (5 segundos)
    });
});
