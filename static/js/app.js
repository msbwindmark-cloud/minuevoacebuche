/**
 * App JS - Centro Ecuestre El Acebuche
 * SweetAlert2 toasts + AJAX con CSRF
 */

/** Muestra un toast con SweetAlert2 */
function toast({icon = "success", title = "", timer = 3000} = {}) {
  const Toast = Swal.mixin({
    toast: true,
    position: "top-end",
    showConfirmButton: false,
    timer: timer,
    timerProgressBar: true,
    didOpen: (toast) => {
      toast.addEventListener("mouseenter", Swal.stopTimer);
      toast.addEventListener("mouseleave", Swal.resumeTimer);
    },
  });
  return Toast.fire({icon: icon, title: title});
}

/** Muestra una alerta simple */
function alerta({icon = "info", title = "Aviso", text = ""} = {}) {
  return Swal.fire({icon: icon, title: title, text: text, timer: 4000, timerProgressBar: true});
}

/** Confirma una acción */
function confirmar({title = "¿Estás seguro?", text = "", confirmText = "Sí, continuar"} = {}) {
  return Swal.fire({
    title: title,
    text: text,
    icon: "question",
    showCancelButton: true,
    confirmButtonText: confirmText,
    cancelButtonText: "Cancelar",
    reverseButtons: true,
  });
}

/** Petición fetch con CSRF incluido */
async function fetchJson(url, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-CSRFToken": window.CSRF_TOKEN || "",
    ...options.headers,
  };
  const resp = await fetch(url, {
    ...options,
    headers: headers,
  });
  if (!resp.ok) {
    throw new Error(`Error ${resp.status}`);
  }
  return await resp.json();
}

/** Cambia el estado de una reserva (AJAX) */
async function cambiarEstadoReserva(reservaId, nuevoEstadoId, btn) {
  const confirmado = await confirmar({
    title: "Cambiar estado de la reserva",
    text: "¿Quieres cambiar el estado de esta reserva?",
    confirmText: "Sí, cambiar",
  });
  if (!confirmado.isConfirmed) return;

  // Estado de carga en el botón
  const textoOriginal = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-arrow-repeat spin"></i>';

  try {
    const data = await fetchJson(
      `/reserva/${reservaId}/cambiar-estado/`,
      {method: "POST", body: JSON.stringify({estado_id: nuevoEstadoId})}
    );

    if (data.ok) {
      toast({icon: "success", title: "Estado actualizado: " + data.nuevo_estado});
      // Actualizar badge del estado si existe en el DOM
      const badge = document.querySelector(`[data-estado-badge="${reservaId}"]`);
      if (badge) {
        badge.textContent = data.nuevo_estado;
        badge.className = "badge bg-" + colorParaClase(data.color);
      }
      // Recargar para reflejar cambios si estamos en la lista
      setTimeout(() => window.location.reload(), 800);
    } else {
      throw new Error(data.error || "No se pudo cambiar el estado");
    }
  } catch (err) {
    console.error(err);
    alerta({icon: "error", title: "Error", text: err.message});
  } finally {
    btn.disabled = false;
    btn.innerHTML = textoOriginal;
  }
}

/** Clase de color Bootstrap a partir del color del evento */
function colorParaClase(color) {
  const mapa = {
    amarillo: "warning",
    rojo: "danger",
    verde: "success",
    gris: "secondary",
  };
  return mapa[color] || "secondary";
}

/** Inicializar botones de cambio de estado al cargar */
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("[data-action=cambiar-estado]").forEach((btn) => {
    btn.addEventListener("click", function () {
      const reservaId = this.dataset.reservaId;
      const nuevoEstadoId = this.dataset.nuevoEstadoId;
      cambiarEstadoReserva(reservaId, nuevoEstadoId, this);
    });
  });
});
