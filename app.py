"""
╔══════════════════════════════════════════════════════╗
║  DULCE MALIA — Pastelería Artesanal                   ║
║  Aplicación principal Flask                            ║
╚══════════════════════════════════════════════════════╝
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import os
import secrets
import json

app = Flask(__name__)

# ──────────────────────────────────────────────
# SECRET_KEY: obligatoria en producción.
# Si no está seteada, generamos una aleatoria de arranque
# (las sesiones se invalidan en cada reinicio, pero NUNCA
# queda una clave fija y conocida dando vueltas en el código).
# ──────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print("⚠️  ADVERTENCIA: no hay SECRET_KEY configurada en las variables de entorno.")
    print("⚠️  Se generó una clave temporal — las sesiones se cerrarán en cada reinicio.")
    print("⚠️  Configurá SECRET_KEY en Render (Environment) para producción.")
app.config['SECRET_KEY'] = SECRET_KEY

# ──────────────────────────────────────────────
# BASE DE DATOS: PostgreSQL en Render, SQLite local
# ──────────────────────────────────────────────
database_url = os.environ.get('DATABASE_URL', 'sqlite:///dulce_malia.db')

# Render entrega URLs con prefijo "postgres://" pero SQLAlchemy requiere "postgresql://"
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,   # verifica la conexión antes de usarla
    'pool_recycle': 300,     # recicla conexiones cada 5 minutos
}

app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

WHATSAPP_NUMBER = os.environ.get('WHATSAPP_NUMBER', '541130614355')

db = SQLAlchemy(app)


# ══════════════════════════════════════════════
# MODELOS DE BASE DE DATOS
# ══════════════════════════════════════════════
class Administrador(db.Model):
    __tablename__ = 'administradores'
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Categoria(db.Model):
    __tablename__ = 'categorias'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    emoji = db.Column(db.String(10), default='🎂')
    orden = db.Column(db.Integer, default=0)
    productos = db.relationship('Producto', backref='categoria', lazy=True)


class Producto(db.Model):
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
    __tablename__ = 'pedidos'
    id = db.Column(db.Integer, primary_key=True)
    nombre_cliente = db.Column(db.String(150), nullable=False)
    telefono = db.Column(db.String(30), nullable=False)
    direccion = db.Column(db.Text)
    comentarios = db.Column(db.Text)
    metodo_pago = db.Column(db.String(50), default='efectivo')
    total = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(30), default='pendiente')
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    detalles = db.relationship('DetallePedido', backref='pedido', lazy=True)


class DetallePedido(db.Model):
    __tablename__ = 'detalle_pedidos'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    nombre_producto = db.Column(db.String(150))
    producto = db.relationship('Producto')


# ══════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ══════════════════════════════════════════════
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def generar_mensaje_whatsapp(pedido, detalles):
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
# RUTAS PÚBLICAS
# ══════════════════════════════════════════════
@app.route('/')
def index():
    destacados = Producto.query.filter_by(destacado=True, disponible=True).limit(8).all()
    categorias = Categoria.query.order_by(Categoria.orden).all()
    return render_template('index.html', destacados=destacados, categorias=categorias, whatsapp=WHATSAPP_NUMBER)


@app.route('/menu')
def menu():
    categorias = Categoria.query.order_by(Categoria.orden).all()
    return render_template('menu.html', categorias=categorias, whatsapp=WHATSAPP_NUMBER)


@app.route('/api/productos')
def api_productos():
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
    data = request.get_json()
    if not data or not data.get('carrito') or not data.get('cliente'):
        return jsonify({'error': 'Datos incompletos'}), 400

    cliente = data['cliente']
    carrito = data['carrito']
    total = sum(item['precio'] * item['cantidad'] for item in carrito)

    pedido = Pedido(
        nombre_cliente=cliente.get('nombre', ''),
        telefono=cliente.get('telefono', ''),
        direccion=cliente.get('direccion', ''),
        comentarios=cliente.get('comentarios', ''),
        metodo_pago=cliente.get('metodo_pago', 'efectivo'),
        total=total
    )
    db.session.add(pedido)
    db.session.flush()

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
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin')
@login_required
def admin_dashboard():
    total_productos = Producto.query.count()
    total_pedidos = Pedido.query.count()
    pedidos_pendientes = Pedido.query.filter_by(estado='pendiente').count()
    pedidos_recientes = Pedido.query.order_by(Pedido.creado_en.desc()).limit(10).all()
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
    productos = Producto.query.order_by(Producto.categoria_id).all()
    categorias = Categoria.query.all()
    return render_template('admin/productos.html', productos=productos, categorias=categorias)


@app.route('/admin/productos/nuevo', methods=['GET', 'POST'])
@login_required
def admin_nuevo_producto():
    categorias = Categoria.query.all()
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        precio = float(request.form.get('precio', 0))
        categoria_id = int(request.form.get('categoria_id'))
        descripcion = request.form.get('descripcion', '')
        stock = int(request.form.get('stock', 99))
        destacado = 'destacado' in request.form
        disponible = 'disponible' in request.form

        imagen_nombre = 'default_cake.png'
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                imagen_nombre = filename

        producto = Producto(
            nombre=nombre, precio=precio, categoria_id=categoria_id,
            descripcion=descripcion, stock=stock, destacado=destacado,
            disponible=disponible, imagen=imagen_nombre
        )
        db.session.add(producto)
        db.session.commit()
        flash('¡Producto agregado exitosamente! 🎂', 'success')
        return redirect(url_for('admin_productos'))

    return render_template('admin/form_producto.html', categorias=categorias, producto=None)


@app.route('/admin/productos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_editar_producto(id):
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
    producto = Producto.query.get_or_404(id)
    producto.disponible = False
    db.session.commit()
    flash('Producto desactivado correctamente.', 'info')
    return redirect(url_for('admin_productos'))


@app.route('/admin/pedidos')
@login_required
def admin_pedidos():
    estado = request.args.get('estado', '')
    if estado:
        pedidos = Pedido.query.filter_by(estado=estado).order_by(Pedido.creado_en.desc()).all()
    else:
        pedidos = Pedido.query.order_by(Pedido.creado_en.desc()).all()
    return render_template('admin/pedidos.html', pedidos=pedidos, estado_filtro=estado)


@app.route('/admin/pedidos/<int:id>')
@login_required
def admin_detalle_pedido(id):
    pedido = Pedido.query.get_or_404(id)
    wa_link = generar_mensaje_whatsapp(pedido, pedido.detalles)
    return render_template('admin/detalle_pedido.html', pedido=pedido, wa_link=wa_link)


@app.route('/admin/pedidos/estado/<int:id>', methods=['POST'])
@login_required
def admin_cambiar_estado(id):
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
    with app.app_context():
        db.create_all()

        if not Administrador.query.first():
            # La contraseña inicial SIEMPRE sale de una variable de entorno.
            # Si no está seteada, se genera una aleatoria y se imprime UNA
            # sola vez en los logs de arranque para que la copies y la
            # cambies desde el panel admin cuanto antes.
            admin_password = os.environ.get('ADMIN_PASSWORD')
            password_generada = False
            if not admin_password:
                admin_password = secrets.token_urlsafe(12)
                password_generada = True

            admin = Administrador(usuario=os.environ.get('ADMIN_USUARIO', 'admin'))
            admin.set_password(admin_password)
            db.session.add(admin)

            if password_generada:
                print("=" * 60)
                print("🔑 Se creó el usuario admin con una contraseña generada:")
                print(f"   Usuario:    {admin.usuario}")
                print(f"   Contraseña: {admin_password}")
                print("   Guardala ahora y cambiala desde el panel admin.")
                print("   Para fijar tu propia contraseña, configurá la")
                print("   variable de entorno ADMIN_PASSWORD en Render.")
                print("=" * 60)

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

            productos_data = [
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
                {'nombre': 'Pastafrola de Membrillo', 'precio': 7000, 'categoria_id': 3, 'destacado': True,
                 'descripcion': 'Masa crocante con abundante dulce de membrillo artesanal'},
                {'nombre': 'Pastafrola de Batata', 'precio': 7000, 'categoria_id': 3,
                 'descripcion': 'Rellena generosamente con dulce de batata casero'},
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
# Inicializar siempre (necesario para gunicorn en Render)
inicializar_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
