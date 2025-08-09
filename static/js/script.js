let retoActual = "";

function girarRuleta() {
  fetch("/hot_roulette/girar", { method: "POST" })
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        alert(data.error);
        return;
      }
      const reto = data.reto;
      retoActual = reto;

      let anguloFinal = Math.random() * 360 + 1440;
      let duracion = 4000;
      canvas.style.transition = `transform ${duracion}ms cubic-bezier(0.33, 1, 0.68, 1)`;
      canvas.style.transform = `rotate(${anguloFinal}deg)`;

      setTimeout(() => {
        document.getElementById("resultado").innerText = "👉 Reto: " + reto;
        actualizarTokens(data.tokens);
        canvas.style.transition = 'none';
        canvas.style.transform = 'rotate(0deg)';
        anguloInicio = 0;
        dibujarRuleta();

        // Mostrar botones
        document.getElementById("btnPublicarReto").style.display = "inline-block";
        document.getElementById("btnEnviarReto").style.display = "inline-block";
      }, duracion);
    })
    .catch(() => {
      alert("Ocurrió un error al girar la ruleta.");
    });
}

document.getElementById("btnPublicarReto").addEventListener("click", () => {
  if (!retoActual) return alert("No hay reto para publicar.");

  fetch("/hot_roulette/publicar_reto", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reto: retoActual })
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        alert("¡Reto publicado con éxito!");
        document.getElementById("btnPublicarReto").style.display = "none";
        retoActual = "";
        location.reload();
      } else {
        alert(data.message || "Error al publicar reto");
      }
    });
});

// ✅ NUEVA FUNCIÓN: Enviar reto a otro jugador
document.getElementById("btnEnviarReto").addEventListener("click", () => {
  if (!retoActual) return alert("No hay reto para enviar.");

  const jugador = prompt("Ingresa el nombre o ID del jugador destinatario:");
  if (!jugador) return;

  fetch("/hot_roulette/enviar_reto", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reto: retoActual, destinatario: jugador })
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        alert("¡Reto enviado correctamente!");
        document.getElementById("btnEnviarReto").style.display = "none";
        retoActual = "";
      } else {
        alert(data.message || "Error al enviar el reto");
      }
    })
    .catch(() => {
      alert("Ocurrió un error al enviar el reto.");
    });
});
