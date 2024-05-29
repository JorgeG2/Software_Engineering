from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, current_app, send_from_directory
)
from flask_login import login_user, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from .extensions import db
from .models import User, Message, PropertyListing, Photos, Reservation, Review
from sqlalchemy.exc import IntegrityError
import os
from datetime import datetime, timedelta



main_bp = Blueprint('main', __name__)



@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Checks if user already exists
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already registered.')
            return redirect(url_for('main.register'))
        
        # Creates new user with hashed password
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('main.login'))
    
    return render_template('register.html')


############################################################### Here is the code for the login route.

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('main.admin_dashboard'))
            else:  
                return redirect(url_for('main.index'))
        else:
            flash('Invalid email or password.')  

    return render_template('login.html')

# Here we will start working on the messaging feature. We will create two routes: one for the user and one for the admin.

@main_bp.route('/send_message', methods=['POST'])
@login_required
def send_message():
  data = request.get_json()
  content = data.get('content')
  new_message = Message(sender_id=current_user.id, recipient_id=1, content=content)

  # Save the new message to the database
  db.session.add(new_message)
  db.session.commit()

  return jsonify({'message': 'Message sent successfully', 'content': content})
##########################################################################shows the messages with owner 

@main_bp.route('/get_my_conversation_with_owner')
@login_required
def get_my_conversation_with_owner():
    messages = Message.query.filter(
        (Message.sender_id == current_user.id) | 
        (Message.recipient_id == current_user.id)
    ).order_by(Message.timestamp.asc()).all()

    messages_data = [{
        'id': message.id,
        'sender_id': message.sender_id,
        'recipient_id': message.recipient_id,
        'content': message.content,
        'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'read': message.read
    } for message in messages]

    return jsonify(messages=messages_data)



# Here is the code for the admin route.###################################################

@main_bp.route('/get_user_list')
@login_required
def get_user_list():
    if not current_user.is_admin:
        # Ensure only admin users can access this route
        return jsonify({'error': 'Unauthorized'}), 403

    # Example: Fetching user IDs and names who have sent messages
    user_list_query = db.session.query(
        Message.sender_id,
        User.name
    ).join(User, User.id == Message.sender_id).distinct()

    user_list = [{'sender_id': user.sender_id, 'name': user.name} for user in user_list_query.all()]

    return jsonify({'user_list': user_list})

#################################################################### for viewing client messages
@main_bp.route('/admin_messages/<int:user_id>')
@login_required
def admin_messages(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    user = User.query.get(user_id)
    messages = Message.query.filter(
        (Message.sender_id == user_id) & (Message.recipient_id == current_user.id) | 
        (Message.sender_id == current_user.id) & (Message.recipient_id == user_id)
    ).order_by(Message.timestamp.asc()).all()

    return render_template('admin_messages.html', user=user, messages=messages)
#################################################################### for deleting client messages
@main_bp.route('/delete_user_messages', methods=['POST'])
@login_required
def delete_user_messages():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    sender_id = request.json.get('sender_id')
    try:
       
        Message.query.filter_by(sender_id=sender_id).delete()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

#################################################################### for sending client messages
#owner messages client
@main_bp.route('/send_message_to_user/<int:user_id>', methods=['POST'])
@login_required
def send_message_to_user(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json
    new_message = Message(sender_id=current_user.id, recipient_id=user_id, content=data['content'])
    db.session.add(new_message)
    db.session.commit()

    return jsonify({'message': 'Message sent successfully'})

#################################################################### for creating a new property listing
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main_bp.route('/create_property_listing', methods=['POST'])
@login_required
def create_property_listing():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'images' not in request.files:
            flash('No images part')
            return redirect(request.url)
        
        images = request.files.getlist('images')
        # in this if block we are checking if the file is present or not.
        if not images or any(image.filename == '' for image in images):
            flash('No image selected for uploading')
            return redirect(request.url)
        uploaded_filenames = []
        for image in images:
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                image.save(image_path)
                uploaded_filenames.append(filename)
            else:
                flash('Allowed image types are -> jpg, jpeg, png')
                return redirect(request.url)
        
        bedrooms = request.form.get('bedrooms')
        bathrooms = request.form.get('bathrooms')
        title = request.form.get('title')
        description = request.form.get('description')
        price = request.form.get('price')
        location = request.form.get('location')
        
        try:
            price = int(price)
        except ValueError:
            flash('Price must be a number.')
            return redirect(url_for('main.admin_dashboard'))
        
        try:
           bedrooms = int(request.form.get('bedrooms'))
           bathrooms = int(request.form.get('bathrooms'))
        except ValueError:
            flash('Bedrooms and Bathrooms must be numbers.')
            return redirect(url_for('main.admin_dashboard'))
        
        new_property = PropertyListing(title=title, description=description, price=price, location=location, bedrooms=bedrooms, bathrooms=bathrooms )
        db.session.add(new_property)
        db.session.flush()  

        for filename in uploaded_filenames:
            new_photo = Photos(photo=filename, property_id=new_property.id)
            db.session.add(new_photo)
        
        db.session.commit()
        flash('Property listing created successfully.')
        
        return redirect(url_for('main.admin_dashboard'))
#################################################################### Deleting property listing
@main_bp.route('/delete_property/<int:property_id>', methods=['POST'])
@login_required
def delete_property(property_id):
    if not current_user.is_admin:
        flash('Unauthorized access.', 'danger')
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # First delete all related data
        Photos.query.filter_by(property_id=property_id).delete()
        Reservation.query.filter_by(property_id=property_id).delete()
        Review.query.filter_by(property_id=property_id).delete()

        # Then delete the property listing
        property_to_delete = PropertyListing.query.get_or_404(property_id)
        db.session.delete(property_to_delete)

        db.session.commit()
        flash('Property and all related data deleted successfully.', 'success')
        return jsonify({'message': 'Property and all related data deleted successfully'})
    except Exception as e:
        db.session.rollback()
        flash('Failed to delete property and related data.', 'danger')
        return jsonify({'error': str(e)}), 500

    
    
######################################################################## for updating property listing
@main_bp.route('/update_property/<int:property_id>', methods=['POST'])
@login_required
def update_property(property_id):
    if not current_user.is_admin:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('main.index'))  # Redirecting to the home if not admin

    property_to_update = PropertyListing.query.get_or_404(property_id)
    try:
        property_to_update.title = request.form['title']
        property_to_update.description = request.form['description']
        property_to_update.bedrooms = int(request.form['bedrooms'])
        property_to_update.bathrooms = int(request.form['bathrooms'])
        property_to_update.price = int(request.form['price'])
        property_to_update.location = request.form['location']

        # Updating photos if any new ones are provided
        photos_to_add = request.files.getlist('photos')
        if photos_to_add and photos_to_add[0].filename:  # Check if at least one photo has a filename
            Photos.query.filter_by(property_id=property_id).delete()  # Delete old photos
            for photo in photos_to_add:
                if allowed_file(photo.filename):
                    filename = secure_filename(photo.filename)
                    photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    photo.save(photo_path)
                    new_photo = Photos(photo=filename, property_id=property_id)
                    db.session.add(new_photo)

        db.session.commit()
        flash('Property updated successfully.')
        return redirect(url_for('main.admin_dashboard')) 
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to update property: {str(e)}', 'error')
        return redirect(url_for('main.edit_property', property_id=property_id))

    
################################################################## for loging out admin from the dashboard
@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index')) 

######################################################################## for setting file location
@main_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    upload_folder = '/Users/jorgegonzales/Desktop/WebsiteImages'
    return send_from_directory(upload_folder, filename)

####################################################################### for viewing property listings
@main_bp.route('/get_property_listings')
def get_property_listings():
    property_listings = PropertyListing.query.all()
    properties = []
    for property in property_listings:
        first_photo = Photos.query.filter_by(property_id=property.id).first()
        photo_url = url_for('main.uploaded_file', filename=first_photo.photo) if first_photo else None
        properties.append({
            'id': property.id,
            'title': property.title,
            'description': property.description,
            'price': property.price,
            'location': property.location,
            'bedrooms': property.bedrooms,
            'bathrooms': property.bathrooms,
            'photo_url': photo_url
        })
    return jsonify(properties)
####################################################################### for sender user to loging page
#this route will redirect the user to the login page.
@main_bp.route('/login_page')
def login_page():
    return redirect(url_for('main.login'))
######################################################################### Creates a reservation
#this route will be used to create a reservation for a property listing.
@main_bp.route('/create_reservation/<int:property_id>', methods=['POST'])
@login_required
def create_reservation(property_id):
    try:
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format. Please use YYYY-MM-DD.')
        return redirect(url_for('main.property_detail', property_id=property_id))

    if start_date < datetime.today() or end_date < datetime.today():
        flash('Cannot select dates in the past.')
        return redirect(url_for('main.property_detail', property_id=property_id))
    
    # Check for overlapping reservations
    existing_reservations = Reservation.query.filter(
        Reservation.property_id == property_id,
        Reservation.end_date >= start_date,
        Reservation.start_date <= end_date
    ).all()

    if existing_reservations:
        flash(f'Unable to reserve from {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}. These dates are already booked. Please choose different dates.')
        return redirect(url_for('main.property_detail', property_id=property_id))

    # Calculate the number of days of the reservation
    delta = end_date - start_date
    reservation_days = delta.days + 1  

    property = PropertyListing.query.get_or_404(property_id)
    base_price = property.price

    six_months_from_now = datetime.today() + timedelta(days=30*6)
    discount = 0
    if start_date >= six_months_from_now:
        discount = 0.1  # 10% discount for bookings made at least 6 months in advance

    total_price_before_discount = base_price * reservation_days
    discounted_total_price = total_price_before_discount - (total_price_before_discount * discount)

    new_reservation = Reservation(
        property_id=property_id,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        status='pending',
        total=discounted_total_price  
    )
    db.session.add(new_reservation)

    try:
        db.session.commit()
        flash_message = f'Your reservation has been made successfully! Total cost: ${discounted_total_price:.2f}'
        if discount > 0:
            flash_message += f' (including a {discount*100}% discount for booking 6 months in advance.)'
        flash(flash_message)

        return redirect(url_for('main.checkout', reservation_id=new_reservation.id))

    except IntegrityError:
        db.session.rollback()
        flash('An error occurred. Please try again.')

    return redirect(url_for('main.property_detail', property_id=property_id))


############################################################################### User dashboard

@main_bp.route('/user_dashboard')
@login_required
def user_dashboard():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('main.admin_dashboard'))
        else:
            user_reservations = db.session.query(Reservation, PropertyListing)\
                .join(PropertyListing, Reservation.property_id == PropertyListing.id)\
                .filter(Reservation.user_id == current_user.id).all()
            
            return render_template('User_dashboard.html', user=current_user, user_reservations=user_reservations)
    else:
        flash('Unauthorized access. Please log in to access this page.', 'error')
        return redirect(url_for('main.login'))
    
############################################################## New route for deleting a reservation
@main_bp.route('/delete_reservation/<int:reservation_id>', methods=['POST'])
@login_required
def delete_reservation(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    if reservation.user_id != current_user.id:
        flash('Unauthorized to delete this reservation.', 'error')
        return redirect(url_for('main.user_dashboard'))

    db.session.delete(reservation)
    db.session.commit()

    flash('Reservation deleted successfully.')
    return redirect(url_for('main.user_dashboard'))

################################################################### New route for deleting a user account
@main_bp.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user_id = request.form.get('user_id')
    if user_id != str(current_user.id):
        flash('Unauthorized to delete this account.', 'error')
        return redirect(url_for('main.user_dashboard'))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    logout_user()
    flash('Your account has been deleted successfully.')
    return redirect(url_for('main.index'))


############################################################################### for viewing searched property listings
@main_bp.route('/search_property_listings')
def search_property_listings():
    bedrooms = request.args.get('bedrooms', type=int)
    bathrooms = request.args.get('bathrooms', type=int)
    price = request.args.get('price', type=int)

    query = PropertyListing.query

    if bedrooms:
        query = query.filter(PropertyListing.bedrooms == bedrooms)
    if bathrooms:
        query = query.filter(PropertyListing.bathrooms == bathrooms)
    if price:
        query = query.filter(PropertyListing.price <= price)

    properties = query.all()

    properties_data = [{
        'id': prop.id,
        'title': prop.title,
        'bedrooms': prop.bedrooms,
        'bathrooms': prop.bathrooms,
        'price': prop.price,
        'first_photo_url': prop.photos[0].photo if prop.photos else None
    } for prop in properties]

    return jsonify(properties_data)
#################################################################### shows Reviews
@main_bp.route('/reviews/<int:property_id>')
def get_reviews(property_id):
    property = PropertyListing.query.get_or_404(property_id)
    reviews = property.reviews.order_by(Review.timestamp.desc()).all()
    reviews_data = [{'author': review.author, 'text': review.text, 'timestamp': review.timestamp.strftime('%Y-%m-%d %H:%M:%S')} for review in reviews]
    return jsonify(reviews_data)

#################################################################### Add a review
@main_bp.route('/reviews/add', methods=['POST'])
@login_required
def add_review():
    property_id = request.form['property_id']
    text = request.form['text']
    author = current_user.name
    
    review = Review(author=author, text=text, property_id=property_id)
    db.session.add(review)
    db.session.commit()
    
    return redirect(url_for('main.property_detail', property_id=property_id))
    

####################################################################
# Route to display detailed view of a specific property
# This route fetches a property by its ID, retrieves the associated photos,
# constructs URLs for those photos using a named endpoint that serves files directly,
# and then renders a template to display the property details including its images.
@main_bp.route('/property/<int:property_id>')
def property_detail(property_id):
    property_listing = PropertyListing.query.get_or_404(property_id)
    # Make sure to use the correct function name in your url_for
    photo_urls = [url_for('main.an_uploaded_file', filename=photo.photo) for photo in property_listing.photos]
    return render_template('property.html', property=property_listing, photo_urls=photo_urls)



####################################################################
# Route to render the edit page for a specific property
# This route is protected by login and further, it checks if the logged-in user is an admin.
# Only admins are allowed to edit properties. If an unauthorized access is attempted,
# a JSON error message is returned. If authorized, it fetches the property by ID and
# displays an edit form pre-filled with the property's existing details.
@main_bp.route('/edit_property/<int:property_id>')
@login_required
def edit_property(property_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    property_to_edit = PropertyListing.query.get_or_404(property_id)
    return render_template('edit_property.html', property=property_to_edit)


@main_bp.route('/uploads/<filename>')
def an_uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)



@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/user_messages')
@login_required
def user_messages():
    if current_user.is_admin:
        return redirect(url_for('main.index'))  
    return render_template('user_messages.html')

@main_bp.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for('main.index'))  
    return render_template('admin_dashboard.html')

@main_bp.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')

#########################################################################

@main_bp.route('/checkout/<int:reservation_id>')
@login_required
def checkout(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    if reservation.user_id != current_user.id:
        flash('You do not have permission to access this reservation.', 'warning')
        return redirect(url_for('main.index'))

    property_listing = PropertyListing.query.get_or_404(reservation.property_id)
    return render_template('checkout.html', reservation=reservation, property=property_listing)

@main_bp.route('/confirm_reservation/<int:reservation_id>', methods=['POST'])
@login_required
def confirm_reservation(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    if reservation.user_id != current_user.id:
        flash('You do not have permission to confirm this reservation.', 'warning')
        return redirect(url_for('main.index'))

    reservation.status = 'confirmed'
    db.session.commit()
    
    flash('Your reservation has been confirmed!', 'success')
    return redirect(url_for('main.user_dashboard'))

###############################################################################

@main_bp.route('/get_reservations')
@login_required
def get_reservations():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    reservations = Reservation.query.all()
    reservation_data = []
    for reservation in reservations:
        property = PropertyListing.query.get(reservation.property_id)
        reservation_info = {
            'reservation_id': reservation.id,
            'property_title': property.title,
            'customer_name': User.query.get(reservation.user_id).name,
            'start_date': reservation.start_date.strftime('%Y-%m-%d'),
            'end_date': reservation.end_date.strftime('%Y-%m-%d'),
            'total': str(reservation.total)
        }
        reservation_data.append(reservation_info)


    return jsonify(reservation_data)

