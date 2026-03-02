import os
import uuid
import bcrypt
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from flask import (
    Flask, render_template, request, redirect, 
    url_for, flash, session, jsonify, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from PIL import Image
import moviepy.editor as mp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///memories.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['ALLOWED_EXTENSIONS'] = {
    'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 
    'avi', 'mkv', 'webm', '3gp', 'm4v'
}

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your memories.'

# Create upload directories
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'photos'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails'), exist_ok=True)

# ==================== Database Models ====================

class User(UserMixin, db.Model):
    """User model for authentication"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    memories = db.relationship('Memory', backref='owner', lazy=True, cascade='all, delete-orphan')
    albums = db.relationship('Album', backref='owner', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def check_password(self, password):
        """Verify password"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

class Memory(db.Model):
    """Memory model for photos and videos"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # 'photo' or 'video'
    mime_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)  # in bytes
    thumbnail = db.Column(db.String(500))
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    duration = db.Column(db.Float)  # for videos
    location = db.Column(db.String(200))
    tags = db.Column(db.String(500))  # comma-separated tags
    is_favorite = db.Column(db.Boolean, default=False)
    is_private = db.Column(db.Boolean, default=True)  # True means only owner can see
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    album_id = db.Column(db.Integer, db.ForeignKey('album.id'), nullable=True)
    
    def get_file_path(self):
        """Get the full file path"""
        return os.path.join(app.config['UPLOAD_FOLDER'], self.file_type + 's', self.filename)
    
    def get_thumbnail_path(self):
        """Get the thumbnail path"""
        if self.thumbnail:
            return os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', self.thumbnail)
        return None
    
    def to_dict(self):
        """Convert to dictionary for JSON responses"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'filename': self.filename,
            'file_type': self.file_type,
            'thumbnail': url_for('static', filename=f'uploads/thumbnails/{self.thumbnail}') if self.thumbnail else None,
            'file_url': url_for('static', filename=f'uploads/{self.file_type}s/{self.filename}'),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'is_favorite': self.is_favorite,
            'location': self.location,
            'tags': self.tags.split(',') if self.tags else []
        }

class Album(db.Model):
    """Album model for organizing memories"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    cover_image = db.Column(db.String(500))
    is_private = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    memories = db.relationship('Memory', backref='album', lazy=True)

# ==================== Forms ====================

class LoginForm(FlaskForm):
    """Login form"""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')

class RegisterForm(FlaskForm):
    """Registration form"""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])

class MemoryForm(FlaskForm):
    """Memory upload/edit form"""
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description')
    location = StringField('Location', validators=[Length(max=200)])
    tags = StringField('Tags (comma-separated)')
    is_private = BooleanField('Private (only you can see)')

# ==================== Helper Functions ====================

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_file_type(filename):
    """Determine if file is photo or video"""
    ext = filename.rsplit('.', 1)[1].lower()
    photo_exts = {'png', 'jpg', 'jpeg', 'gif'}
    video_exts = {'mp4', 'mov', 'avi', 'mkv', 'webm', '3gp', 'm4v'}
    
    if ext in photo_exts:
        return 'photo'
    elif ext in video_exts:
        return 'video'
    return None

def create_thumbnail(image_path, thumbnail_path, size=(300, 300)):
    """Create thumbnail for image"""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumbnail_path, 'JPEG')
            return True
    except Exception as e:
        print(f"Error creating thumbnail: {e}")
        return False

def get_video_info(video_path):
    """Get video information"""
    try:
        video = mp.VideoFileClip(video_path)
        duration = video.duration
        width, height = video.size
        
        # Create thumbnail from first frame
        thumbnail_filename = f"thumb_{uuid.uuid4().hex}.jpg"
        thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', thumbnail_filename)
        video.save_frame(thumbnail_path, t=0)
        video.close()
        
        return {
            'duration': duration,
            'width': width,
            'height': height,
            'thumbnail': thumbnail_filename
        }
    except Exception as e:
        print(f"Error processing video: {e}")
        return None

# ==================== Routes ====================

@app.route('/')
def index():
    """Home page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        # Check if user exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'danger')
            return render_template('register.html', form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'danger')
            return render_template('register.html', form=form)
        
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data
        )
        user.set_password(form.password.data)
        
        # Make first user admin
        if User.query.count() == 0:
            user.is_admin = True
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    # Get statistics
    total_memories = Memory.query.filter_by(user_id=current_user.id).count()
    total_photos = Memory.query.filter_by(user_id=current_user.id, file_type='photo').count()
    total_videos = Memory.query.filter_by(user_id=current_user.id, file_type='video').count()
    favorites = Memory.query.filter_by(user_id=current_user.id, is_favorite=True).count()
    
    # Get recent memories
    recent_memories = Memory.query.filter_by(user_id=current_user.id)\
        .order_by(Memory.created_at.desc())\
        .limit(6)\
        .all()
    
    # Get albums
    albums = Album.query.filter_by(user_id=current_user.id)\
        .order_by(Album.created_at.desc())\
        .limit(4)\
        .all()
    
    return render_template(
        'dashboard.html',
        total_memories=total_memories,
        total_photos=total_photos,
        total_videos=total_videos,
        favorites=favorites,
        recent_memories=recent_memories,
        albums=albums
    )

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload memories"""
    form = MemoryForm()
    
    # Get user's albums for dropdown
    albums = Album.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Secure filename and generate unique name
            original_filename = secure_filename(file.filename)
            file_ext = original_filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
            
            # Determine file type
            file_type = get_file_type(original_filename)
            
            if not file_type:
                flash('Invalid file type', 'danger')
                return redirect(request.url)
            
            # Save file
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{file_type}s', unique_filename)
            file.save(upload_path)
            file_size = os.path.getsize(upload_path)
            
            # Create memory object
            memory = Memory(
                title=form.title.data or original_filename,
                description=form.description.data,
                filename=unique_filename,
                file_type=file_type,
                mime_type=file.mimetype,
                file_size=file_size,
                location=form.location.data,
                tags=form.tags.data,
                is_private=form.is_private.data,
                user_id=current_user.id
            )
            
            # Process based on file type
            if file_type == 'photo':
                # Get image dimensions
                with Image.open(upload_path) as img:
                    memory.width, memory.height = img.size
                
                # Create thumbnail
                thumbnail_filename = f"thumb_{unique_filename.rsplit('.', 1)[0]}.jpg"
                thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', thumbnail_filename)
                create_thumbnail(upload_path, thumbnail_path)
                memory.thumbnail = thumbnail_filename
            
            else:  # video
                video_info = get_video_info(upload_path)
                if video_info:
                    memory.duration = video_info['duration']
                    memory.width = video_info['width']
                    memory.height = video_info['height']
                    memory.thumbnail = video_info['thumbnail']
            
            # Set album if selected
            album_id = request.form.get('album')
            if album_id:
                album = Album.query.get(album_id)
                if album and album.user_id == current_user.id:
                    memory.album_id = album.id
            
            db.session.add(memory)
            db.session.commit()
            
            flash('Memory uploaded successfully!', 'success')
            return redirect(url_for('gallery'))
        
        else:
            flash('File type not allowed', 'danger')
    
    return render_template('upload.html', form=form, albums=albums)

@app.route('/gallery')
@login_required
def gallery():
    """Gallery view"""
    # Get filter parameters
    filter_type = request.args.get('type', 'all')  # all, photos, videos
    filter_album = request.args.get('album')
    filter_favorite = request.args.get('favorite')
    search = request.args.get('search')
    
    # Base query
    query = Memory.query.filter_by(user_id=current_user.id)
    
    # Apply filters
    if filter_type == 'photos':
        query = query.filter_by(file_type='photo')
    elif filter_type == 'videos':
        query = query.filter_by(file_type='video')
    
    if filter_album:
        query = query.filter_by(album_id=filter_album)
    
    if filter_favorite:
        query = query.filter_by(is_favorite=True)
    
    if search:
        query = query.filter(
            db.or_(
                Memory.title.contains(search),
                Memory.description.contains(search),
                Memory.tags.contains(search),
                Memory.location.contains(search)
            )
        )
    
    # Order by date
    memories = query.order_by(Memory.created_at.desc()).all()
    
    # Get albums for filter
    albums = Album.query.filter_by(user_id=current_user.id).all()
    
    return render_template('gallery.html', memories=memories, albums=albums)

@app.route('/memory/<int:memory_id>')
@login_required
def view_memory(memory_id):
    """View single memory"""
    memory = Memory.query.get_or_404(memory_id)
    
    # Check permissions
    if memory.user_id != current_user.id:
        flash('You don\'t have permission to view this memory', 'danger')
        return redirect(url_for('gallery'))
    
    # Increment view count
    memory.view_count += 1
    db.session.commit()
    
    # Get next and previous memories
    prev_memory = Memory.query.filter(
        Memory.user_id == current_user.id,
        Memory.id < memory_id
    ).order_by(Memory.id.desc()).first()
    
    next_memory = Memory.query.filter(
        Memory.user_id == current_user.id,
        Memory.id > memory_id
    ).order_by(Memory.id.asc()).first()
    
    return render_template(
        'memory.html',
        memory=memory,
        prev_memory=prev_memory,
        next_memory=next_memory
    )

@app.route('/memory/<int:memory_id>/edit', methods=['POST'])
@login_required
def edit_memory(memory_id):
    """Edit memory details"""
    memory = Memory.query.get_or_404(memory_id)
    
    if memory.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.get_json()
    
    if 'title' in data:
        memory.title = data['title']
    if 'description' in data:
        memory.description = data['description']
    if 'location' in data:
        memory.location = data['location']
    if 'tags' in data:
        memory.tags = data['tags']
    if 'is_favorite' in data:
        memory.is_favorite = data['is_favorite']
    if 'is_private' in data:
        memory.is_private = data['is_private']
    
    db.session.commit()
    
    return jsonify({'success': True, 'memory': memory.to_dict()})

@app.route('/memory/<int:memory_id>/delete', methods=['POST'])
@login_required
def delete_memory(memory_id):
    """Delete memory"""
    memory = Memory.query.get_or_404(memory_id)
    
    if memory.user_id != current_user.id:
        flash('Permission denied', 'danger')
        return redirect(url_for('gallery'))
    
    # Delete files
    try:
        file_path = memory.get_file_path()
        if os.path.exists(file_path):
            os.remove(file_path)
        
        if memory.thumbnail:
            thumb_path = memory.get_thumbnail_path()
            if thumb_path and os.path.exists(thumb_path):
                os.remove(thumb_path)
    except Exception as e:
        print(f"Error deleting files: {e}")
    
    db.session.delete(memory)
    db.session.commit()
    
    flash('Memory deleted successfully', 'success')
    return redirect(url_for('gallery'))

@app.route('/albums')
@login_required
def albums():
    """View all albums"""
    user_albums = Album.query.filter_by(user_id=current_user.id)\
        .order_by(Album.created_at.desc()).all()
    return render_template('albums.html', albums=user_albums)

@app.route('/albums/create', methods=['POST'])
@login_required
def create_album():
    """Create new album"""
    data = request.get_json()
    
    album = Album(
        name=data['name'],
        description=data.get('description', ''),
        is_private=data.get('is_private', True),
        user_id=current_user.id
    )
    
    db.session.add(album)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'album': {
            'id': album.id,
            'name': album.name,
            'description': album.description
        }
    })

@app.route('/albums/<int:album_id>/add-memory', methods=['POST'])
@login_required
def add_to_album(album_id):
    """Add memory to album"""
    album = Album.query.get_or_404(album_id)
    
    if album.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.get_json()
    memory_id = data.get('memory_id')
    
    memory = Memory.query.get_or_404(memory_id)
    if memory.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    memory.album_id = album.id
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/search')
@login_required
def search():
    """Search memories"""
    query = request.args.get('q', '')
    
    if not query:
        return redirect(url_for('gallery'))
    
    results = Memory.query.filter(
        Memory.user_id == current_user.id,
        db.or_(
            Memory.title.contains(query),
            Memory.description.contains(query),
            Memory.tags.contains(query),
            Memory.location.contains(query)
        )
    ).order_by(Memory.created_at.desc()).all()
    
    return render_template('search.html', results=results, query=query)

@app.route('/favorites')
@login_required
def favorites():
    """View favorite memories"""
    favorites = Memory.query.filter_by(
        user_id=current_user.id,
        is_favorite=True
    ).order_by(Memory.updated_at.desc()).all()
    
    return render_template('favorites.html', memories=favorites)

@app.route('/timeline')
@login_required
def timeline():
    """View memories on timeline"""
    memories = Memory.query.filter_by(user_id=current_user.id)\
        .order_by(Memory.created_at.desc()).all()
    
    # Group by year and month
    timeline_data = {}
    for memory in memories:
        year = memory.created_at.strftime('%Y')
        month = memory.created_at.strftime('%B')
        
        if year not in timeline_data:
            timeline_data[year] = {}
        
        if month not in timeline_data[year]:
            timeline_data[year][month] = []
        
        timeline_data[year][month].append(memory)
    
    return render_template('timeline.html', timeline=timeline_data)

@app.route('/api/stats')
@login_required
def api_stats():
    """API endpoint for statistics"""
    total = Memory.query.filter_by(user_id=current_user.id).count()
    photos = Memory.query.filter_by(user_id=current_user.id, file_type='photo').count()
    videos = Memory.query.filter_by(user_id=current_user.id, file_type='video').count()
    favorites = Memory.query.filter_by(user_id=current_user.id, is_favorite=True).count()
    
    # Get monthly uploads for chart
    from sqlalchemy import func, extract
    monthly = db.session.query(
        extract('year', Memory.created_at).label('year'),
        extract('month', Memory.created_at).label('month'),
        func.count(Memory.id).label('count')
    ).filter_by(user_id=current_user.id)\
     .group_by('year', 'month')\
     .order_by('year', 'month')\
     .limit(12)\
     .all()
    
    return jsonify({
        'total': total,
        'photos': photos,
        'videos': videos,
        'favorites': favorites,
        'monthly': [{'month': f"{m.year}-{int(m.month):02d}", 'count': m.count} for m in monthly]
    })

# ==================== Main Entry Point ====================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
