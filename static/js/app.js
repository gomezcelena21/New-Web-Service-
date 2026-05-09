/**
 * ╔══════════════════════════════════════════════════╗
 * ║     DULCE MALIA — JavaScript principal           ║
 * ║     Maneja: carrito, checkout, animaciones       ║
 * ╚══════════════════════════════════════════════════╝
 */

let carrito = JSON.parse(localStorage.getItem('dulcemalia_carrito') || '[]');

function guardarCarrito() {
  localStorage.setItem('dulcemalia_carrito', JSON.stringify(carrito));
}

window.addEventListener('scroll', () => {
  const navbar = document.querySelector('.navbar');
  if (navbar) {
    navbar.classList.toggle('scrolled', window.scrollY > 40);
  }
});

const hamburger = document.querySelector('.hamburger');
const navLinks = document.querySelector('.nav-links');
if (hamburger && navLinks) {
  hamburger.addEventListener('click', () => {
    navLinks.classList.toggle('abierto');
  });
}

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry, i) => {
    if (entry.isIntersecting) {
      setTimeout(() => entry.target.classList.add('visible'), i * 80);
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

function agregarAlCarrito(id, nombre, precio, emoji = '🎂') {
  const existente = carrito.find(item => item.id === id);

  if (existente) {
    existente.cantidad++;
  } else {
    carrito.push({ id, nombre, precio, cantidad: 1, emoji });
  }

  guardarCarrito();
  actualizarUI();
  mostrarToast(`¡${nombre} agregado al carrito! 🎂`, 'success');

  const btn = document.querySelector(`[data-producto-id="${id}"]`);
  if (btn) {
    btn.classList.add('agregado');
    btn.textContent = '✓ Agregado';
    setTimeout(() => {
      btn.classList.remove('agregado');
      btn.innerHTML = '+ Agregar';
    }, 1500);
  }
}

function cambiarCantidad(id, cambio) {
  const item = carrito.find(i => i.id === id);
  if (!item) return;

  item.cantidad += cambio;
  if (item.cantidad <= 0) {
    carrito = carrito.filter(i => i.id !== id);
  }

  guardarCarrito();
  actualizarUI();
  renderizarCarritoPanel();
}

function eliminarDelCarrito(id) {
  carrito = carrito.filter(i => i.id !== id);
  guardarCarrito();
  actualizarUI();
  renderizarCarritoPanel();
}

function vaciarCarrito() {
  carrito = [];
  guardarCarrito();
  actualizarUI();
  renderizarCarritoPanel();
}

function actualizarUI() {
  const totalItems = carrito.reduce((sum, item) => sum + item.cantidad, 0);
  const badge = document.querySelector('.carrito-badge');
  if (badge) {
    badge.textContent = totalItems;
    badge.classList.toggle('visible', totalItems > 0);
  }
}

function renderizarCarritoPanel() {
  const contenedor = document.getElementById('carrito-items');
  const totalEl = document.getElementById('carrito-total');
  if (!contenedor) return;

  if (carrito.length === 0) {
    contenedor.innerHTML = `
      <div class="carrito-vacio">
        <span class="vacio-emoji">🛍️</span>
        <p>Tu carrito está vacío.<br>¡Elige tus dulces favoritos!</p>
      </div>`;
    if (totalEl) totalEl.textContent = '$0';
    return;
  }

  contenedor.innerHTML = carrito.map(item => `
    <div class="carrito-item">
      <div class="carrito-item-emoji">${item.emoji}</div>
      <div class="carrito-item-info">
        <div class="carrito-item-nombre">${item.nombre}</div>
        <div class="carrito-item-precio">$${item.precio.toLocaleString('es-AR')}</div>
      </div>
      <div class="carrito-item-controles">
        <button class="ctrl-btn" onclick="cambiarCantidad(${item.id}, -1)">−</button>
        <span class="ctrl-cantidad">${item.cantidad}</span>
        <button class="ctrl-btn" onclick="cambiarCantidad(${item.id}, 1)">+</button>
        <button class="carrito-eliminar" onclick="eliminarDelCarrito(${item.id})" title="Eliminar">🗑️</button>
      </div>
    </div>
  `).join('');

  const total = carrito.reduce((sum, item) => sum + item.precio * item.cantidad, 0);
  if (totalEl) totalEl.textContent = '$' + total.toLocaleString('es-AR');
}

function abrirCarrito() {
  renderizarCarritoPanel();
  document.getElementById('carrito-overlay')?.classList.add('activo');
  document.getElementById('carrito-panel')?.classList.add('activo');
  document.body.style.overflow = 'hidden';
}

function cerrarCarrito() {
  document.getElementById('carrito-overlay')?.classList.remove('activo');
  document.getElementById('carrito-panel')?.classList.remove('activo');
  document.body.style.overflow = '';
}

document.getElementById('carrito-overlay')?.addEventListener('click', cerrarCarrito);

function abrirCheckout() {
  if (carrito.length === 0) {
    mostrarToast('Primero agrega productos al carrito 🛍️', 'error');
    return;
  }
  cerrarCarrito();
  setTimeout(() => {
    document.getElementById('checkout-modal')?.classList.add('activo');
    document.body.style.overflow = 'hidden';
  }, 300);
}

function cerrarCheckout() {
  document.getElementById('checkout-modal')?.classList.remove('activo');
  document.body.style.overflow = '';
}

async function enviarPedido() {
  const nombre = document.getElementById('ch-nombre')?.value.trim();
  const telefono = document.getElementById('ch-telefono')?.value.trim();
  const direccion = document.getElementById('ch-direccion')?.value.trim();
  const comentarios = document.getElementById('ch-comentarios')?.value.trim();
  const metodo_pago = document.querySelector('input[name="pago"]:checked')?.value || 'efectivo';

  if (!nombre || !telefono) {
    mostrarToast('Por favor completá nombre y teléfono 📱', 'error');
    return;
  }

  const btnEnviar = document.getElementById('btn-enviar-pedido');
  if (btnEnviar) {
    btnEnviar.disabled = true;
    btnEnviar.textContent = 'Enviando...';
  }

  try {
    const response = await fetch('/realizar-pedido', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        carrito: carrito,
        cliente: { nombre, telefono, direccion, comentarios, metodo_pago }
      })
    });

    const data = await response.json();

    if (data.success) {
      cerrarCheckout();
      vaciarCarrito();
      mostrarToast('¡Pedido enviado! Redirigiendo a WhatsApp... 🎉', 'success');

      setTimeout(() => {
        window.open(data.whatsapp_link, '_blank');
      }, 1000);
    } else {
      mostrarToast('Error al enviar el pedido. Intentá de nuevo.', 'error');
    }
  } catch (error) {
    console.error('Error:', error);
    mostrarToast('Error de conexión. Contactanos por WhatsApp.', 'error');
  } finally {
    if (btnEnviar) {
      btnEnviar.disabled = false;
      btnEnviar.textContent = '🛒 Confirmar Pedido';
    }
  }
}

async function cargarProductos(categoria_id = null) {
  const contenedor = document.getElementById('productos-dinamicos');
  if (!contenedor) return;

  contenedor.innerHTML = '<div style="text-align:center;padding:40px;color:#9B8B8B;">Cargando productos... 🎂</div>';

  let url = '/api/productos';
  if (categoria_id) url += `?categoria_id=${categoria_id}`;

  try {
    const resp = await fetch(url);
    const productos = await resp.json();

    if (productos.length === 0) {
      contenedor.innerHTML = '<div style="text-align:center;padding:40px;color:#9B8B8B;">No hay productos disponibles en esta categoría.</div>';
      return;
    }

    const emojis = { 'Bizcochuelos': '🎂', 'Budines': '🍮', 'Pastafrolas': '🥧', 'Postres': '🍰' };

    contenedor.innerHTML = productos.map(p => {
      const emoji = emojis[p.categoria] || '🍰';
      const tieneImagen = p.imagen && p.imagen !== 'default_cake.png';

      return `
        <div class="producto-card reveal">
          <div class="producto-imagen-wrap">
            ${tieneImagen
              ? `<img src="${p.imagen}" alt="${p.nombre}" class="producto-imagen">`
              : `<div class="producto-imagen-placeholder">
                   <span class="ph-emoji">${emoji}</span>
                   <span class="ph-texto">${p.categoria}</span>
                 </div>`
            }
            <span class="producto-badge-cat">${p.categoria}</span>
          </div>
          <div class="producto-info">
            <h3 class="producto-nombre">${p.nombre}</h3>
            <p class="producto-desc">${p.descripcion || ''}</p>
            <div class="producto-footer">
              <div class="producto-precio">
                <span>$</span>${p.precio.toLocaleString('es-AR')}
              </div>
              <button
                class="btn-agregar"
                data-producto-id="${p.id}"
                onclick="agregarAlCarrito(${p.id}, '${p.nombre.replace(/'/g, "\\'")}', ${p.precio}, '${emoji}')">
                + Agregar
              </button>
            </div>
          </div>
        </div>`;
    }).join('');

    document.querySelectorAll('.producto-card.reveal').forEach(el => observer.observe(el));

  } catch (err) {
    console.error('Error cargando productos:', err);
    contenedor.innerHTML = '<div style="text-align:center;padding:40px;color:#e74c3c;">Error cargando productos 😢</div>';
  }
}

function configurarFiltros() {
  document.querySelectorAll('[data-filtro]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-filtro]').forEach(b => b.classList.remove('activo'));
      btn.classList.add('activo');

      const categoriaId = btn.dataset.filtro === 'todos' ? null : btn.dataset.filtro;
      cargarProductos(categoriaId);
    });
  });
}

function mostrarToast(mensaje, tipo = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${tipo}`;
  toast.innerHTML = `<span>${tipo === 'success' ? '✅' : '❌'}</span> ${mensaje}`;
  container.appendChild(toast);

  setTimeout(() => toast.remove(), 3200);
}

document.addEventListener('DOMContentLoaded', () => {
  actualizarUI();
  cargarProductos();
  configurarFiltros();

  document.getElementById('checkout-modal')?.addEventListener('click', function(e) {
    if (e.target === this) cerrarCheckout();
  });
});
