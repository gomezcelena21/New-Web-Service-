"""
╔══════════════════════════════════════════════════════╗
║          DULCE MALIA — Pastelería Artesanal          ║
║          Aplicación principal Flask                  ║
╚══════════════════════════════════════════════════════╝

Este archivo es el corazón de la aplicación.
Flask es un "micro-framework" de Python: es liviano, flexible y muy
fácil de aprender. Cada "ruta" (@app.route) define una URL de la tienda.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import os
import json

# ──────────────────────────────────────────────
# CONFIGURACIÓN DE LA APLICACIÓN
# ──────────────────────────────────────────────
app = Flask(__name__)

# SECRET_KEY: clave para cifrar las sesiones (cookies).
# En producción, cámbiala por algo largo y aleatorio.
app.config['SECRET_KEY'] = 'dulce_malia_secret_2024_cambia_esto_en_produccion'

# Base de datos SQLite. El archivo se crea automáticamente en /instance/
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dulce_malia.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Carpeta donde se guardan las imágenes subidas por el admin
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB máximo por imagen

# Extensiones de imagen permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# WhatsApp del dueño (sin +, sin espacios)
WHATSAPP_NUMBER = "541130614355"

# Inicializar SQLAlchemy
db = SQLAlchemy(app)
with app.pp_context():
    db.create_all()


# ══════════════════════════════════════════════
# MODELOS DE BASE DE DATOS
# Cada clase = una tabla en SQLite
# ══════════════════════════════════════════════

class Administrador(db.Model):
    """
    Tabla: administradores
    Guarda los usuarios con acceso al panel de administración.
    """
    __tablename__ = 'administradores'
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        """Encripta la contraseña antes de guardarla."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica si la contraseña ingresada coincide con la guardada."""
        return check_password_hash(self.password_hash, password)


class Categoria(db.Model):
    """
    Tabla: categorias
    Agrupa los productos (ej: Bizcochuelos, Budines, Postres)
    Relación: Una categoría tiene MUCHOS productos (1:N)
    """
    __tablename__ = 'categorias'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    emoji = db.Column(db.String(10), default='🎂')
    orden = db.Column(db.Integer, default=0)
    # backref crea automáticamente categoria.productos para acceder a sus productos
    productos = db.relationship('Producto', backref='categoria', lazy=True)


class Producto(db.Model):
    """
    Tabla: productos
    Cada fila es un producto de la pastelería.
    Relación: Pertenece a UNA categoría (N:1)
    """
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    precio = db.Column(db.Float, nullable=False)
    imagen = db.Column(db.String(255), default='default_cake.png')
    stock = db.Column(db.Integer, default=99)
    disponible = db.Column(db.Boolean, default=True)
    destacado = db.Column(db.Boolean, default=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)


class Pedido(db.Model):
    """
    Tabla: pedidos
    Guarda cada pedido completo con los datos del cliente.
    Relación: Un pedido tiene MUCHOS detalles (1:N)
    """
    __tablename__ = 'pedidos'
    id = db.Column(db.Integer, primary_key=True)
    # Datos del cliente
    nombre_cliente = db.Column(db.String(150), nullable=False)
    telefono = db.Column(db.String(30), nullable=False)
    direccion = db.Column(db.Text)
    comentarios = db.Column(db.Text)
    # Pago y estado
    metodo_pago = db.Column(db.String(50), default='efectivo')  # efectivo | transferencia | mercadopago
    total = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(30), default='pendiente')  # pendiente | preparando | listo | entregado
    # Fecha
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    # Relación con detalles
    detalles = db.relationship('DetallePedido', backref='pedido', lazy=True)


class DetallePedido(db.Model):
    """
    Tabla: detalle_pedidos
    Cada fila es un producto dentro de un pedido.
    Relación N:1 con Pedido y N:1 con Producto.

    Ejemplo: si alguien pide 2 chocotortas y 1 flan,
    se crean 2 filas en esta tabla (una por cada producto).
    """
    __tablename__ = 'detalle_pedidos'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario = db.Column(db.Float, nullable=False)  # precio al momento de la compra
    subtotal = db.Column(db.Float, nullable=False)
    # Guardamos el nombre por si el producto se elimina después
    nombre_producto = db.Column(db.String(150))
    producto = db.relationship('Producto')


# ══════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ══════════════════════════════════════════════

def allowed_file(filename):
    """Verifica que el archivo sea una imagen permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    """
    Decorador de Python: protege rutas del admin.
    Si no hay sesión activa, redirige al login.
    Los decoradores (@login_required) se "envuelven" alrededor de una función.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def generar_mensaje_whatsapp(pedido, detalles):
    """
    Genera el texto del mensaje de WhatsApp con todos los datos del pedido.
    La URL wa.me permite abrir WhatsApp con un mensaje pre-escrito.
    """
    lineas = [
        f"🍰 *NUEVO PEDIDO - Dulce Malia*",
        f"━━━━━━━━━━━━━━━━━━",
        f"👤 *Cliente:* {pedido.nombre_cliente}",
        f"📱 *Teléfono:* {pedido.telefono}",
        f"📍 *Dirección:* {pedido.direccion or 'No especificada'}",
        f"",
        f"🛒 *Productos:*",
    ]
    for d in detalles:
        lineas.append(f"  • {d.nombre_producto} x{d.cantidad} — ${d.subtotal:,.0f}")

    lineas += [
        f"",
        f"💰 *Total:* ${pedido.total:,.0f}",
        f"💳 *Pago:* {pedido.metodo_pago.title()}",
    ]
    if pedido.comentarios:
        lineas.append(f"📝 *Comentarios:* {pedido.comentarios}")

    mensaje = "\n".join(lineas)
    import urllib.parse
    return f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(mensaje)}"


# ══════════════════════════════════════════════
# RUTAS PÚBLICAS (Tienda)
# ══════════════════════════════════════════════

@app.route('/')
def index():
    """
    Ruta principal: muestra la página de inicio.
    Carga productos destacados y categorías para el hero y las secciones.
    """
    destacados = Producto.query.filter_by(destacado=True, disponible=True).limit(8).all()
    categorias = Categoria.query.order_by(Categoria.orden).all()
    return render_template('index.html',
                           destacados=destacados,
                           categorias=categorias,
                           whatsapp=WHATSAPP_NUMBER)


@app.route('/menu')
def menu():
    """Muestra todos los productos organizados por categoría."""
    categorias = Categoria.query.order_by(Categoria.orden).all()
    return render_template('menu.html', categorias=categorias, whatsapp=WHATSAPP_NUMBER)


@app.route('/api/productos')
def api_productos():
    """
    API REST: devuelve productos en formato JSON.
    El frontend JavaScript llama a esta URL para cargar productos dinámicamente.
    """
    categoria_id = request.args.get('categoria_id')
    if categoria_id:
        productos = Producto.query.filter_by(categoria_id=categoria_id, disponible=True).all()
    else:
        productos = Producto.query.filter_by(disponible=True).all()

    return jsonify([{
        'id': p.id,
        'nombre': p.nombre,
        'descripcion': p.descripcion,
        'precio': p.precio,
        'imagen': p.imagen,
        'stock': p.stock,
        'categoria': p.categoria.nombre
    } for p in productos])


@app.route('/realizar-pedido', methods=['POST'])
def realizar_pedido():
    """
    Procesa el pedido enviado desde el carrito.
    1. Valida los datos
    2. Guarda el pedido en la base de datos
    3. Genera el link de WhatsApp
    4. Devuelve confirmación
    """
    data = request.get_json()

    # Validar que vengan los datos mínimos
    if not data or not data.get('carrito') or not data.get('cliente'):
        return jsonify({'error': 'Datos incompletos'}), 400

    cliente = data['cliente']
    carrito = data['carrito']

    # Calcular total
    total = sum(item['precio'] * item['cantidad'] for item in carrito)

    # Crear el pedido principal
    pedido = Pedido(
        nombre_cliente=cliente.get('nombre', ''),
        telefono=cliente.get('telefono', ''),
        direccion=cliente.get('direccion', ''),
        comentarios=cliente.get('comentarios', ''),
        metodo_pago=cliente.get('metodo_pago', 'efectivo'),
        total=total
    )
    db.session.add(pedido)
    db.session.flush()  # Obtener el ID antes de hacer commit

    # Crear los detalles del pedido
    detalles = []
    for item in carrito:
        producto = Producto.query.get(item['id'])
        if producto:
            detalle = DetallePedido(
                pedido_id=pedido.id,
                producto_id=item['id'],
                cantidad=item['cantidad'],
                precio_unitario=item['precio'],
                subtotal=item['precio'] * item['cantidad'],
                nombre_producto=item['nombre']
            )
            db.session.add(detalle)
            detalles.append(detalle)

    db.session.commit()

    # Generar link de WhatsApp
    wa_link = generar_mensaje_whatsapp(pedido, detalles)

    return jsonify({
        'success': True,
        'pedido_id': pedido.id,
        'whatsapp_link': wa_link,
        'mensaje': '¡Pedido creado! Redirigiendo a WhatsApp...'
    })


# ══════════════════════════════════════════════
# RUTAS DEL PANEL ADMINISTRADOR
# ══════════════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Login del administrador."""
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        password = request.form.get('password')
        admin = Administrador.query.filter_by(usuario=usuario).first()

        if admin and admin.check_password(password):
            session['admin_id'] = admin.id
            session['admin_usuario'] = admin.usuario
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')

    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    """Cierra la sesión del admin."""
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin')
@login_required
def admin_dashboard():
    """Panel principal con estadísticas."""
    total_productos = Producto.query.count()
    total_pedidos = Pedido.query.count()
    pedidos_pendientes = Pedido.query.filter_by(estado='pendiente').count()
    pedidos_recientes = Pedido.query.order_by(Pedido.creado_en.desc()).limit(10).all()
    # Ingresos del mes
    from sqlalchemy import extract
    ingresos = db.session.query(db.func.sum(Pedido.total)).filter(
        Pedido.estado != 'cancelado'
    ).scalar() or 0

    return render_template('admin/dashboard.html',
                           total_productos=total_productos,
                           total_pedidos=total_pedidos,
                           pedidos_pendientes=pedidos_pendientes,
                           pedidos_recientes=pedidos_recientes,
                           ingresos=ingresos)


@app.route('/admin/productos')
@login_required
def admin_productos():
    """Lista todos los productos."""
    productos = Producto.query.order_by(Producto.categoria_id).all()
    categorias = Categoria.query.all()
    return render_template('admin/productos.html', productos=productos, categorias=categorias)


@app.route('/admin/productos/nuevo', methods=['GET', 'POST'])
@login_required
def admin_nuevo_producto():
    """Formulario para agregar un nuevo producto."""
    categorias = Categoria.query.all()

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        precio = float(request.form.get('precio', 0))
        categoria_id = int(request.form.get('categoria_id'))
        descripcion = request.form.get('descripcion', '')
        stock = int(request.form.get('stock', 99))
        destacado = 'destacado' in request.form
        disponible = 'disponible' in request.form

        # Manejar subida de imagen
        imagen_nombre = 'default_cake.png'
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Agregar timestamp para evitar duplicados
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                imagen_nombre = filename

        producto = Producto(
            nombre=nombre,
            precio=precio,
            categoria_id=categoria_id,
            descripcion=descripcion,
            stock=stock,
            destacado=destacado,
            disponible=disponible,
            imagen=imagen_nombre
        )
        db.session.add(producto)
        db.session.commit()
        flash('¡Producto agregado exitosamente! 🎂', 'success')
        return redirect(url_for('admin_productos'))

    return render_template('admin/form_producto.html', categorias=categorias, producto=None)


@app.route('/admin/productos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_editar_producto(id):
    """Editar un producto existente."""
    producto = Producto.query.get_or_404(id)
    categorias = Categoria.query.all()

    if request.method == 'POST':
        producto.nombre = request.form.get('nombre')
        producto.precio = float(request.form.get('precio', 0))
        producto.categoria_id = int(request.form.get('categoria_id'))
        producto.descripcion = request.form.get('descripcion', '')
        producto.stock = int(request.form.get('stock', 99))
        producto.destacado = 'destacado' in request.form
        producto.disponible = 'disponible' in request.form

        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                producto.imagen = filename

        db.session.commit()
        flash('¡Producto actualizado! ✨', 'success')
        return redirect(url_for('admin_productos'))

    return render_template('admin/form_producto.html', categorias=categorias, producto=producto)


@app.route('/admin/productos/eliminar/<int:id>', methods=['POST'])
@login_required
def admin_eliminar_producto(id):
    """Elimina un producto (soft delete: solo lo marca como no disponible)."""
    producto = Producto.query.get_or_404(id)
    producto.disponible = False
    db.session.commit()
    flash('Producto desactivado correctamente.', 'info')
    return redirect(url_for('admin_productos'))


@app.route('/admin/pedidos')
@login_required
def admin_pedidos():
    """Ver todos los pedidos."""
    estado = request.args.get('estado', '')
    if estado:
        pedidos = Pedido.query.filter_by(estado=estado).order_by(Pedido.creado_en.desc()).all()
    else:
        pedidos = Pedido.query.order_by(Pedido.creado_en.desc()).all()
    return render_template('admin/pedidos.html', pedidos=pedidos, estado_filtro=estado)


@app.route('/admin/pedidos/<int:id>')
@login_required
def admin_detalle_pedido(id):
    """Ver el detalle completo de un pedido."""
    pedido = Pedido.query.get_or_404(id)
    wa_link = generar_mensaje_whatsapp(pedido, pedido.detalles)
    return render_template('admin/detalle_pedido.html', pedido=pedido, wa_link=wa_link)


@app.route('/admin/pedidos/estado/<int:id>', methods=['POST'])
@login_required
def admin_cambiar_estado(id):
    """Cambia el estado de un pedido (pendiente → preparando → listo → entregado)."""
    pedido = Pedido.query.get_or_404(id)
    nuevo_estado = request.form.get('estado')
    estados_validos = ['pendiente', 'preparando', 'listo', 'entregado', 'cancelado']
    if nuevo_estado in estados_validos:
        pedido.estado = nuevo_estado
        db.session.commit()
        flash(f'Estado actualizado a: {nuevo_estado.upper()} ✅', 'success')
    return redirect(url_for('admin_pedidos'))


# ══════════════════════════════════════════════
# INICIALIZACIÓN DE LA BASE DE DATOS
# ══════════════════════════════════════════════

def inicializar_db():
    """
    Crea las tablas y carga datos iniciales si no existen.
    Se llama una sola vez al iniciar la app.
    """
    with app.app_context():
        db.create_all()

        # Crear admin por defecto si no existe
        if not Administrador.query.first():
            admin = Administrador(usuario='admin')
            admin.set_password('dulcemalia2024')
            db.session.add(admin)

        # Crear categorías del menú real
        if not Categoria.query.first():
            categorias_data = [
                {'nombre': 'Bizcochuelos', 'emoji': '🎂', 'orden': 1,
                 'descripcion': 'Esponjosos y perfectos para toda ocasión'},
                {'nombre': 'Budines', 'emoji': '🍮', 'orden': 2,
                 'descripcion': 'Húmedos y deliciosos, ideales para el té'},
                {'nombre': 'Pastafrolas', 'emoji': '🥧', 'orden': 3,
                 'descripcion': 'Clásicas y artesanales con relleno generoso'},
                {'nombre': 'Postres', 'emoji': '🍰', 'orden': 4,
                 'descripcion': 'Irresistibles creaciones para el paladar'},
            ]
            for cd in categorias_data:
                db.session.add(Categoria(**cd))
            db.session.flush()

            # Cargar productos reales del menú de Dulce Malia
            productos_data = [
                # Bizcochuelos
                {'nombre': 'Bizcochuelo Vainilla', 'precio': 4000, 'categoria_id': 1, 'destacado': True,
                 'descripcion': 'Suave y esponjoso bizcochuelo de vainilla pura'},
                {'nombre': 'Bizcochuelo Chocolate', 'precio': 4000, 'categoria_id': 1, 'destacado': True,
                 'descripcion': 'Intenso sabor a chocolate artesanal'},
                {'nombre': 'Bizcochuelo Marmolado', 'precio': 4000, 'categoria_id': 1,
                 'descripcion': 'La combinación perfecta de vainilla y chocolate'},
                {'nombre': 'Bizcochuelo Limón', 'precio': 4000, 'categoria_id': 1,
                 'descripcion': 'Refrescante y aromático con limón natural'},
                {'nombre': 'Bizcochuelo Naranja', 'precio': 4000, 'categoria_id': 1,
                 'descripcion': 'Esponjoso con el dulce sabor de la naranja'},
                {'nombre': 'Bizcochuelo Manzana', 'precio': 6000, 'categoria_id': 1, 'destacado': True,
                 'descripcion': 'Húmedo y especiado, con trozos de manzana real'},
                # Budines
                {'nombre': 'Budín de Vainilla', 'precio': 3500, 'categoria_id': 2,
                 'descripcion': 'Clásico y cremoso budín de vainilla'},
                {'nombre': 'Budín de Chocolate', 'precio': 3500, 'categoria_id': 2,
                 'descripcion': 'Irresistible con cobertura de chocolate'},
                {'nombre': 'Budín Marmolado', 'precio': 3500, 'categoria_id': 2,
                 'descripcion': 'Vainilla y chocolate en perfecta armonía'},
                {'nombre': 'Budín de Limón', 'precio': 3500, 'categoria_id': 2,
                 'descripcion': 'Fresco y ligero con glaseado de limón'},
                {'nombre': 'Budín de Naranja', 'precio': 3500, 'categoria_id': 2,
                 'descripcion': 'Cítrico y húmedo con ralladura de naranja'},
                {'nombre': 'Budín de Manzana', 'precio': 5000, 'categoria_id': 2, 'destacado': True,
                 'descripcion': 'Especiado y con manzana en cada bocado'},
                # Pastafrolas
                {'nombre': 'Pastafrolа de Membrillo', 'precio': 7000, 'categoria_id': 3, 'destacado': True,
                 'descripcion': 'Masa crocante con abundante dulce de membrillo artesanal'},
                {'nombre': 'Pastafrolа de Batata', 'precio': 7000, 'categoria_id': 3,
                 'descripcion': 'Rellena generosamente con dulce de batata casero'},
                # Postres
                {'nombre': 'Postre Oreo', 'precio': 4500, 'categoria_id': 4,
                 'descripcion': 'Cremoso postre con galletas Oreo y crema batida'},
                {'nombre': 'Chocotorta', 'precio': 4500, 'categoria_id': 4, 'destacado': True,
                 'descripcion': 'La clásica chocotorta argentina, cremosa y deliciosa'},
                {'nombre': 'Durazno con Crema', 'precio': 4500, 'categoria_id': 4,
                 'descripcion': 'Fresco postre con duraznos al natural y crema'},
                {'nombre': 'Tiramisú', 'precio': 4500, 'categoria_id': 4, 'destacado': True,
                 'descripcion': 'Auténtico tiramisú italiano con mascarpone y café'},
                {'nombre': 'Gelatina Surtida', 'precio': 2000, 'categoria_id': 4,
                 'descripcion': 'Cerezas, durazno y frambuesa — elige tu favorita'},
                {'nombre': 'Flan Casero', 'precio': 6500, 'categoria_id': 4,
                 'descripcion': 'Cremoso y suave flan con caramelo artesanal'},
                {'nombre': 'Budín de Pan', 'precio': 7000, 'categoria_id': 4,
                 'descripcion': 'El clásico budín de pan casero con pasas y crema'},
            ]
            for pd in productos_data:
                db.session.add(Producto(**pd))

        db.session.commit()
        print("✅ Base de datos inicializada correctamente")


# ══════════════════════════════════════════════
# PUNTO DE ENTRADA
# ══════════════════════════════════════════════

if __name__ == '__main__':
    inicializar_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 
