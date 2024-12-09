# app/routes.py
import datetime
import uuid
import json
from flask import Blueprint, request, redirect, url_for, render_template, session
from .models import db, Users, DigitalGoods, Gekocht, Favoriet, Feedback, Connections, Category, digitalgoods_categories, Messages, Meldingen
from flask import flash
from werkzeug.utils import secure_filename
from .config import supabase
from supabase import Client
from flask import Response
import requests
from flask import jsonify
from .helper import create_notification

main = Blueprint('main', __name__)

@main.route('/')
def index():
    if 'userid' in session:
        user = Users.query.get(session['userid'])
        return render_template('index.html', username=user.firstname, user=user)
    return render_template('index.html', username=None)

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Haal gegevens op uit het formulier
        email = request.form.get('email')
        password = request.form.get('password')  # Zorg dat je wachtwoord veilig opslaat!
        first_name = request.form.get('firstname')
        last_name = request.form.get('lastname')
        address = request.form.get('address')
        city = request.form.get('city')
        postal_code = request.form.get('postalcode')
        country = request.form.get('country')
        nationality = request.form.get('nationality')
        profpic_file = request.files.get('profilePicture')

        # Controleer of de gebruiker al bestaat op basis van email of username
        if Users.query.filter((Users.email == email)).first():
            return "Email or Username already registered", 400

        # Verwerk en upload profielfoto
        profile_picture_url = None
        if profpic_file and profpic_file.filename != '':
            if profpic_file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                image_filename = secure_filename(profpic_file.filename)
                unique_image_filename = f"{uuid.uuid4()}_{image_filename}"
                image_data = profpic_file.read()
                supabase.storage.from_("profile_pictures").upload(f"profile_pictures/{unique_image_filename}", image_data)
                profile_picture_url = supabase.storage.from_("profile_pictures").get_public_url(f"profile_pictures/{unique_image_filename}")
            else:
                return "Ongeldig bestandstype. Upload een afbeelding.", 400

        # Maak een nieuwe gebruiker aan
        new_user = Users(
            userid=str(uuid.uuid4()),  # Genereer een unieke ID
            email=email,
            password=password,  # Hash het wachtwoord
            firstname=first_name,
            lastname=last_name,
            address=address,
            city=city,
            postalcode=postal_code,
            country=country,
            nationality=nationality,
            profilepicture=profile_picture_url
        )

        # Voeg de gebruiker toe aan de database
        db.session.add(new_user)
        db.session.commit()

        create_notification(
            recipient_id=new_user.userid,
            message=f"Welkom {new_user.firstname}, dankjewel om lid te worden van de Traveltalescommunity. Neem een kijkje op de website en geniet van je welkomstgift!"
        )

        # Sla de userid op in de sessie
        session['userid'] = new_user.userid

        return redirect(url_for('main.index'))

    # Bij een GET-verzoek toon het registratieformulier
    return render_template('register.html')

@main.route('/login', methods=['POST','GET'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']  # Zorg dat het wachtwoord ook wordt opgehaald

        # Zoek de gebruiker op basis van het e-mailadres
        user = Users.query.filter_by(email=email).first()

        # Controleer of de gebruiker bestaat
        if user and user.password == password:  # Controleer of het wachtwoord correct is
            session['userid'] = user.userid  # Gebruik de `userid` van de specifieke gebruiker
            return redirect(url_for('main.index'))
        
        # Toon een foutbericht als de gebruiker niet wordt gevonden of het wachtwoord onjuist is
        flash('Ongeldige inloggegevens. Controleer je e-mailadres en wachtwoord.', 'error')
        return redirect(url_for('main.login'))
    
    return render_template('login.html')

@main.route('/logout', methods=['POST', 'GET'])
def logout():
    session.pop('userid', None)
    return redirect(url_for('main.index'))

@main.route('/post', methods=['GET', 'POST'])
def post():
    if 'userid' not in session:
        return redirect(url_for('main.login'))
    user = Users.query.get(session['userid'])  # Huidige gebruiker ophalen
    if not user:
        return redirect(url_for('main.logout'))  # Uitloggen als de gebruiker niet bestaa
    
    error_message = None

    if request.method == 'POST':
        try:
            # Haal formuliergegevens op
            itinerary_name = request.form['titleofitinerary']
            price = float(request.form['price'])
            description_tekst = request.form['descriptionofitinerary']
            pdf_file = request.files['file']
            stad = request.form['start_city']
            image_files = request.files.getlist('images[]')
            selected_categories = request.form.getlist('category_id')
            if not selected_categories:
                raise ValueError("Selecteer minstens één categorie.")
            # Valideer en upload PDF
            if pdf_file and pdf_file.filename.endswith('.pdf'):
                filename = secure_filename(pdf_file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                pdf_data = pdf_file.read()
                supabase.storage.from_("pdf_files").upload(f"pdfs/{unique_filename}", pdf_data)
                public_url = supabase.storage.from_("pdf_files").get_public_url(f"pdfs/{unique_filename}")
            else:
                raise ValueError("Ongeldig bestandstype. Upload een PDF-bestand.")

            # Haal coördinaten op voor de startstad
            api_url = f"https://nominatim.openstreetmap.org/search"
            params = {
                'q': stad,
                'format': 'json',
                'limit': 1,
                'accept-language': 'nl'
            }
            headers = {'User-Agent': 'MyApp/1.0 (vermeulen.anna@outlook.be)'}
            try:
                response = requests.get(api_url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
                if data and len(data) > 0:
                    latitude = str(data[0]['lat'])
                    longitude = str(data[0]['lon'])
                else:
                    latitude = None
                    longitude = None
            except requests.RequestException as e:
                print(f"Fout bij het ophalen van coördinaten: {e}")
                latitude = None
                longitude = None

            # Valideer en upload afbeeldingen
            image_urls = []
            for image_file in image_files:
                if image_file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    image_filename = secure_filename(image_file.filename)
                    unique_image_filename = f"{uuid.uuid4()}_{image_filename}"
                    image_data = image_file.read()
                    supabase.storage.from_("travel_images").upload(f"images/{unique_image_filename}", image_data)
                    image_public_url = supabase.storage.from_("travel_images").get_public_url(f"images/{unique_image_filename}")
                    image_urls.append(image_public_url)

            # Voeg toe aan database
            new_itinerary = DigitalGoods(
                goodid=str(uuid.uuid4()),
                titleofitinerary=itinerary_name,
                descriptionofitinerary=description_tekst,
                userid=session['userid'],
                price=price,
                pdf_url=public_url,
                image_urls=json.dumps(image_urls),  # Opslaan als JSON string
                start_city=stad,
                latitude=latitude,
                longitude=longitude
            )
            for category_id in selected_categories:
                category = Category.query.get(category_id)
                if category:
                    new_itinerary.categories.append(category)

            db.session.add(new_itinerary)
            db.session.commit()

            followers = Connections.query.filter_by(followed_id=session['userid']).all()
            for follower in followers:
                create_notification(
                    recipient_id=follower.follower_id,
                    sender_id=session['userid'],
                    good_id=new_itinerary.goodid,
                    message=f"{user.firstname} {user.lastname}, die je volgt, heeft een nieuwe reis gepost: '{itinerary_name}'."
                )


            return redirect(url_for('main.reistoegevoegd'))

        except ValueError as ve:
            error_message = str(ve)
        except Exception as e:
            print(f"Error: {e}")
            db.session.rollback()
            error_message = "Er ging iets mis bij het opslaan van de reis."
    categories = Category.query.all()
    return render_template('post.html', error_message=error_message, user = user, categories = categories)

@main.route('/userpage', methods=['GET', 'POST'])
def userpage():
    if 'userid' not in session:
        return redirect(url_for('main.login'))  # Stuur gebruiker naar login als deze niet is ingelogd
    
    user = Users.query.get(session['userid'])  # Haal de huidige gebruiker op
    if not user:
        return redirect(url_for('main.logout'))  # Log gebruiker uit als de gebruiker niet bestaat

    if request.method == 'POST':
        # Haal gegevens uit het formulier
        user.firstname = request.form.get('firstname')
        user.lastname = request.form.get('lastname')
        user.email = request.form.get('email')
        user.address = request.form.get('address')
        user.city = request.form.get('city')
        user.postalcode = request.form.get('postalcode')
        user.country = request.form.get('country')
        
        print(f"Aanwezig in request.files: {list(request.files.keys())}")

        profpic_file = request.files.get('profilePicture')
        if profpic_file:
            if profpic_file.filename != '':
                if profpic_file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    try:
                        # Upload nieuwe profielfoto naar Supabase
                        image_filename = secure_filename(profpic_file.filename)
                        unique_filename = f"{uuid.uuid4()}_{image_filename}"
                        image_data = profpic_file.read()
                        
                        # Supabase upload
                        supabase.storage.from_("profile_pictures").upload(f"profile_pictures/{unique_filename}", image_data)
                        profile_picture_url = supabase.storage.from_("profile_pictures").get_public_url(f"profile_pictures/{unique_filename}")
                        
                        # Update database
                        user.profilepicture = profile_picture_url
                        print(f"Profielfoto geüpload: {profile_picture_url}")
                    except Exception as e:
                        print(f"Fout bij uploaden profielfoto: {e}")
                        flash("Fout bij het bijwerken van de profielfoto.", "error")
                else:
                    print("Ongeldig bestandstype.")
                    flash("Ongeldig bestandstype. Alleen JPG, PNG of GIF toegestaan.", "error")
            else:
                print("Leeg bestand ontvangen.")
        else:
            print("Geen bestand ontvangen in 'profilePicture'.")

        # Sla wijzigingen op in de database
        try:
            db.session.commit()
            print("Profiel succesvol opgeslagen.")
        except Exception as e:
            print(f"Fout bij opslaan in database: {e}")
            flash("Fout bij het opslaan van wijzigingen.", "error")

        # Sla wijzigingen op in de database
        db.session.commit()

        return redirect(url_for('main.userpage'))  # Refresh de pagina met de nieuwe gegevens

    return render_template('userpage.html', user=user)

@main.route('/change_password', methods=['POST'])
def change_password():
    user = Users.query.filter_by(userid=session['userid']).first()
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not user or not user.check_password(current_password):
        flash('Huidig wachtwoord is onjuist.', 'error')
        return redirect(url_for('main.userpage'))
    
    if new_password != confirm_password:
        flash('Nieuwe wachtwoorden komen niet overeen.', 'error')
        return redirect(url_for('main.userpage'))

    user.set_password(new_password)  # Zorg dat je een methode `set_password` hebt in je User-model
    db.session.commit()
    flash('Wachtwoord succesvol gewijzigd!', 'success')
    return redirect(url_for('main.userpage'))

@main.route('/download_pdf/<goodid>', methods=['GET'])
def download_pdf(goodid):
    # Haal de reis op uit de database
    reis = DigitalGoods.query.filter_by(goodid=goodid).first()

    if reis:
        # Controleer of een geldige PDF-URL aanwezig is
        if reis.pdf_url:
            pdf_path = reis.pdf_url.split('pdfs/')[1]  # Haal het pad naar de PDF uit de URL
            response = supabase.storage.from_("pdf_files").download(f"pdfs/{pdf_path}")

            if response:
                # Stuur de PDF terug met juiste headers
                return Response(
                    response,
                    mimetype="application/pdf",
                    headers={
                        "Content-Disposition": f"inline; filename={pdf_path}",
                        "Content-Type": "application/pdf"
                    }
                )
        else:
            return "PDF niet gevonden of niet gekoppeld aan deze reis.", 404
    else:
        return "Reis niet gevonden.", 404

@main.route('/gepost', methods=['GET', 'POST'])
def gepost():
    if 'userid' not in session:
        return redirect(url_for('main.login'))  # Verwijzen naar login als gebruiker niet is ingelogd

    user = Users.query.get(session['userid'])  # Huidige gebruiker ophalen
    if not user:
        return redirect(url_for('main.logout'))  # Uitloggen als de gebruiker niet bestaat

    # Geposte reizen van de ingelogde gebruiker ophalen, gesorteerd op nieuwste eerst
    geposte_reizen = DigitalGoods.query.filter_by(userid=user.userid).order_by(DigitalGoods.createdat.desc()).all()

    # Voeg het aantal aankopen toe aan elke reis
    for reis in geposte_reizen:
        reis.aantal_aankopen = Gekocht.query.filter_by(goodid=reis.goodid).count()

    if request.method == 'POST':
        # Update een specifieke reis
        goodid = request.form.get('goodid')  # ID van het item dat wordt bewerkt
        reis = DigitalGoods.query.filter_by(goodid=goodid, userid=user.userid).first()

        if reis:
            # Gegevens updaten vanuit het formulier
            reis.titleofitinerary = request.form.get('titleofitinerary')
            reis.descriptionofitinerary = request.form.get('descriptionofitinerary')
            reis.price = request.form.get('price')

            db.session.commit()  # Wijzigingen opslaan

            return redirect(url_for('main.gepost'))

    return render_template('gepost.html', user=user, geposte_reizen=geposte_reizen)



@main.route('/download_aankoop_pdf/<gekochtid>', methods=['GET'])
def download_aankoop_pdf(gekochtid):
    # Haal de aankoop op uit de database
    aankoop = Gekocht.query.filter_by(gekochtid=gekochtid).first()

    if aankoop:
        # Verkrijg de gekoppelde `DigitalGoods` via de foreign key `goodid`
        reis = DigitalGoods.query.filter_by(goodid=aankoop.goodid).first()
        if reis and reis.pdf_url:
            # Extract het pad naar de PDF uit de URL
            pdf_path = reis.pdf_url.split('pdfs/')[1]  # Pad achter "pdfs/" verkrijgen
            response = supabase.storage.from_("pdf_files").download(f"pdfs/{pdf_path}")

            if response:
                # Retourneer de PDF met de juiste headers
                return Response(
                    response,
                    mimetype="application/pdf",
                    headers={
                        "Content-Disposition": f"inline; filename={pdf_path}",
                        "Content-Type": "application/pdf"
                    }
                )
        else:
            return "PDF niet gevonden of niet gekoppeld aan deze aankoop.", 404
    else:
        return "Aankoop niet gevonden.", 404

@main.route('/gekocht', methods=['GET'])
def gekocht():
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    user = Users.query.get(session['userid'])
    if not user:
        return redirect(url_for('main.logout'))

    # Haal alle gekochte reizen van de gebruiker op
    gekochte_reizen = Gekocht.query.filter_by(userid=user.userid).all()

    # Voeg eigenaarinformatie toe aan elk gekocht object
    for aankoop in gekochte_reizen:
        aankoop.eigenaar = Users.query.get(aankoop.good.userid)

    return render_template('gekocht.html', user=user, gekochte_reizen=gekochte_reizen)

@main.route('/algekocht')
def algekocht():
    if 'userid' not in session:
        return redirect(url_for('main.login'))  # Verwijs naar login als gebruiker niet is ingelogd
    
    user = Users.query.get(session['userid'])  # Huidige gebruiker ophalen
    if not user:
        return redirect(url_for('main.logout'))  # Uitloggen als de gebruiker niet bestaat

    return render_template('algekocht.html', user=user)

@main.route('/favoriet', methods=['GET'])
def favoriet():
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    user = Users.query.get(session['userid'])
    if not user:
        return redirect(url_for('main.logout'))

    # Haal favorieten op voor de huidige gebruiker
    favorieten = Favoriet.query.filter_by(userid=user.userid).all()

    # Voeg eigenaarinformatie toe aan elk favoriet object
    for favoriet in favorieten:
        favoriet.eigenaar = Users.query.get(favoriet.good.userid)

    return render_template('favoriet.html', user=user, favorieten=favorieten)

@main.route('/search', methods=['GET'])
def search():
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    user = Users.query.get(session['userid'])
    if not user:
        return redirect(url_for('main.logout'))

    zoekterm = request.args.get('zoekterm', '').strip()
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    city = request.args.get('city', '').strip().lower()
    selected_categories = request.args.getlist('category_id')
    min_rating = request.args.get('min_rating', type=int)

    available_cities = sorted(set(
        result.start_city.lower() for result in 
        DigitalGoods.query.with_entities(DigitalGoods.start_city).distinct()
        if result.start_city
    ))
    categories = Category.query.all()
    selected_category_names = [
        category.name for category in categories if str(category.categoryid) in selected_categories
    ]

    query = DigitalGoods.query.order_by(DigitalGoods.createdat.desc())

    if zoekterm:
        query = query.filter(DigitalGoods.titleofitinerary.ilike(f'%{zoekterm}%'))
    if min_price is not None:
        query = query.filter(DigitalGoods.price >= min_price)
    if max_price is not None:
        query = query.filter(DigitalGoods.price <= max_price)
    if city:
        query = query.filter(DigitalGoods.start_city.ilike(city))
    if selected_categories:
        query = query.join(digitalgoods_categories).join(Category).filter(
            Category.categoryid.in_(selected_categories)
        )
    if min_rating is not None:
        query = query.filter(
            (db.session.query(db.func.avg(Feedback.rating))
             .filter(Feedback.targetgoodid == DigitalGoods.goodid)
             .correlate(DigitalGoods)
             .label('average_rating')) >= min_rating
        )

    reizen = query.all()

    for reis in reizen:
        reis.user = Users.query.filter_by(userid=reis.userid).first()
        try:
            reis.image_urls = json.loads(reis.image_urls) if reis.image_urls else []
        except json.JSONDecodeError:
            reis.image_urls = []
        reis.review_count = Feedback.query.filter_by(targetgoodid=reis.goodid).count()

        reviews = Feedback.query.filter_by(targetgoodid=reis.goodid).all()
        if reviews:
            reis.gemiddelde_rating = sum(review.rating for review in reviews) / len(reviews)
        else:
            reis.gemiddelde_rating = 0

    favorieten = [favoriet.goodid for favoriet in Favoriet.query.filter_by(userid=session['userid']).all()]

    return render_template(
        'search.html',
        user=user,
        reizen=reizen,
        favorieten=favorieten,
        zoekterm=zoekterm,
        min_price=min_price,
        max_price=max_price,
        city=city,
        available_cities=available_cities,
        categories=categories,
        selected_categories=selected_categories,
        selected_category_names=selected_category_names,
        min_rating=min_rating
    )



@main.route('/reis/<goodid>', methods=['GET'])
def reisdetail(goodid):
    if 'userid' not in session:
        return redirect(url_for('main.login'))  # Verwijzen naar login als gebruiker niet is ingelogd

    user = Users.query.get(session['userid'])  # Huidige gebruiker ophalen
    if not user:
        return redirect(url_for('main.logout'))  # Uitloggen als de gebruiker niet bestaat

    # Haal de specifieke reis op uit de database
    reis = DigitalGoods.query.filter_by(goodid=goodid).first()

    if not reis:
        flash('Reis niet gevonden.', 'error')
        return redirect(url_for('main.search'))

    # Haal afbeelding op

    reis.user = Users.query.filter_by(userid=reis.userid).first()
    try:
        reis.image_urls = json.loads(reis.image_urls) if reis.image_urls else []
    except json.JSONDecodeError:
        reis.image_urls = []
    reis.review_count = Feedback.query.filter_by(targetgoodid=reis.goodid).count()

    reviews = Feedback.query.filter_by(targetgoodid=reis.goodid).all()
    if reviews:
        reis.gemiddelde_rating = sum(review.rating for review in reviews) / len(reviews)
    else:
        reis.gemiddelde_rating = 0


    # Haal de eigenaar van de reis op
    eigenaar = Users.query.filter_by(userid=reis.userid).first()

    # Controleer of deze reis een favoriet is van de gebruiker
    is_favoriet = Favoriet.query.filter_by(userid=user.userid, goodid=goodid).first() is not None

    # Controleer of de gebruiker de eigenaar is van de reis
    is_owner = (user.userid == eigenaar.userid)

    # Haal alle reviews voor deze reis op
    reviews = Feedback.query.filter_by(targetgoodid=goodid).all()
    categorieën = Category.query.join(DigitalGoods.categories).filter(DigitalGoods.goodid == goodid).all()

    # Bereken het gemiddelde van de reviews
    if reviews:
        gemiddelde_rating = int(sum(review.rating for review in reviews) / len(reviews))
    else:
        gemiddelde_rating = 0

    # Voeg het aantal reviews toe
    review_count = len(reviews)

    # Render de template met reisgegevens, reviews, favorietstatus en eigenaar
    return render_template(
        'reisdetail.html',
        reis=reis,
        user=user,
        eigenaar=eigenaar,
        is_favoriet=is_favoriet,
        reviews=reviews,
        review_count=review_count,
        gemiddelde_rating=gemiddelde_rating,
        categorieën=categorieën,
        is_owner=is_owner
    )


@main.route('/koop/<goodid>', methods=['POST'])
def koop(goodid):
    if 'userid' not in session:
        return redirect(url_for('main.login'))  # Verwijs naar login als gebruiker niet is ingelogd

    user = Users.query.get(session['userid'])  # Huidige gebruiker ophalen
    if not user:
        return redirect(url_for('main.logout'))  # Uitloggen als de gebruiker niet bestaat

    # Haal de specifieke reis op uit de database
    reis = DigitalGoods.query.filter_by(goodid=goodid).first()
    if not reis:
        flash('Reis niet gevonden.', 'error')
        return redirect(url_for('main.search'))  # Verwijs terug naar de zoekpagina

    # Controleer of deze reis al gekocht is door de gebruiker
    bestaande_aankoop = Gekocht.query.filter_by(userid=user.userid, goodid=goodid).first()
    if bestaande_aankoop:
        flash('Je hebt deze reis al gekocht.', 'info')
        return redirect(url_for('main.algekocht'))  # Verwijs naar de pagina met gekochte reizen

    # Voeg de aankoop toe aan de database
    nieuwe_aankoop = Gekocht(
    gekochtid=str(uuid.uuid4()),  # Unieke ID voor gekochtid
    userid=user.userid,
    goodid=reis.goodid,
    createdat=datetime.datetime.utcnow()  # Dit wordt standaard gebruikt
    )
    db.session.add(nieuwe_aankoop)
    db.session.commit()

    create_notification(
        recipient_id=reis.userid,  # Veronderstel dat reis een eigenaar heeft
        sender_id=user.userid,
        good_id=goodid,
        message=f" {user.firstname} {user.lastname} heeft je reis '{reis.titleofitinerary}' gekocht!"
    )

    return redirect(url_for('main.koopbevestiging'))

@main.route('/koopbevestiging', methods=['GET'])
def koopbevestiging():
    if 'userid' not in session:
        return redirect(url_for('main.login'))  # Verwijs naar login als gebruiker niet is ingelogd
    
    user = Users.query.get(session['userid'])  # Huidige gebruiker ophalen
    if not user:
        return redirect(url_for('main.logout'))  # Uitloggen als de gebruiker niet bestaat

    return render_template('koopbevestiging.html', user=user)

@main.route('/verwijder_reis', methods=['POST'])
def verwijder_reis():
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    goodid = request.form.get('goodid')
    reis = DigitalGoods.query.filter_by(goodid=goodid, userid=session['userid']).first()

    if reis:
        db.session.delete(reis)
        db.session.commit()
        return redirect(url_for('main.reisverwijderd'))

    flash('Reis kon niet worden gevonden of verwijderd.', 'error')
    return redirect(url_for('main.gepost'))


@main.route('/reisverwijderd', methods=['GET'])
def reisverwijderd():
    return render_template('reisverwijderd.html')

@main.route('/reistoegevoegd', methods=['GET'])
def reistoegevoegd():
    if 'userid' not in session:
        return redirect(url_for('main.login'))  # Verwijs naar login als gebruiker niet is ingelogd
    
    user = Users.query.get(session['userid'])  # Haal de huidige gebruiker op
    if not user:
        return redirect(url_for('main.logout'))  # Uitloggen als de gebruiker niet bestaat

    return render_template('reistoegevoegd.html', user=user)

@main.route('/verwijder_aankoop', methods=['POST'])
def verwijder_aankoop():
    if 'userid' not in session:
        return redirect(url_for('main.login'))
    
    user = Users.query.get(session['userid'])  # Haal de huidige gebruiker op
    if not user:
        return redirect(url_for('main.logout'))

    gekochtid = request.form.get('gekochtid')
    aankoop = Gekocht.query.filter_by(gekochtid=gekochtid).first()

    if aankoop and aankoop.userid == session['userid']:
        db.session.delete(aankoop)
        db.session.commit()
        flash('Aankoop succesvol verwijderd.', 'success')
    else:
        flash('Er is iets misgegaan bij het verwijderen.', 'error')

    return render_template('aankoopverwijderd.html')

@main.route('/toggle_favoriet', methods=['POST'])
def toggle_favoriet():
    if 'userid' not in session:
        flash("Je moet ingelogd zijn om een reis als favoriet te markeren of verwijderen.", "error")
        return redirect(url_for('main.login'))

    user = Users.query.get(session['userid'])

    user_id = session['userid']
    goodid = request.form.get('goodid')
    reis = DigitalGoods.query.filter_by(goodid=goodid).first()
    referer_page = request.form.get('referer')  # Haal de referentiepagina op

    if not goodid:
        flash("Geen geldige reis geselecteerd.", "error")
        return redirect(url_for('main.search'))

    # Controleer of de reis al in de favorieten staat
    favoriet = Favoriet.query.filter_by(userid=user_id, goodid=goodid).first()
    if favoriet:
        # Verwijder de favoriet
        db.session.delete(favoriet)
        db.session.commit()
        #flash("Reis verwijderd uit je favorieten.", "info")
    else:
        # Voeg de favoriet toe
        nieuwe_favoriet = Favoriet(
            favorietid=str(uuid.uuid4()),
            userid=user_id,
            goodid=goodid
        )
        db.session.add(nieuwe_favoriet)
        db.session.commit()

        good = DigitalGoods.query.get(goodid)
        create_notification(
            recipient_id=good.userid,  # Eigenaar van de reis
            sender_id=user_id,  # Huidige gebruiker
            good_id=goodid,
            message=f"{user.firstname} {user.lastname} heeft je reis '{reis.titleofitinerary}' als favoriet gemarkeerd!"
        )

        #flash("Reis toegevoegd aan je favorieten!", "success")

    # Verwijs terug naar de juiste pagina
    if referer_page == 'search':
        return redirect(url_for('main.search'))
    elif referer_page == 'reisdetail':
        return redirect(url_for('main.reisdetail', goodid=goodid))
    elif referer_page == 'favoriet':
        return redirect(url_for('main.favoriet'))
    else:
        return redirect(url_for('main.search'))  # Fallback naar search

@main.route('/review/<goodid>', methods=['GET'])
def review_page(goodid):
    # Haal de digitale goederen op die overeenkomen met het opgegeven goodid
    reis = DigitalGoods.query.filter_by(goodid=goodid).first()

    # Controleer of de reis bestaat
    if not reis:
        flash('De geselecteerde reis bestaat niet.', 'error')
        return redirect(url_for('main.gekocht'))  # Stuur terug naar de gekocht-pagina
    if 'userid' not in session:
        return redirect(url_for('main.login'))
    
    user = Users.query.get(session['userid'])  # Zorg ervoor dat userid in de sessie zit
    if not user:
        return redirect(url_for('main.login'))
    # Render de review-pagina met de reisdetails
    return render_template('review.html', reis=reis)

@main.route('/submit_review', methods=['POST'])
def submit_review():
    if 'userid' not in session:
        flash("Je moet ingelogd zijn om een reis als favoriet te markeren of verwijderen.", "error")
        return redirect(url_for('main.login'))

    userid = session['userid']
    goodid = request.form.get('goodid')
    review_text = request.form.get('review_text')
    rating = request.form.get('rating')

    # Controleer of alle velden correct zijn ingevuld
    if not (goodid and review_text and rating):
        flash('Alle velden zijn verplicht.', 'danger')
        return redirect(request.referrer)

    # Controleer of de gebruiker deze reis heeft gekocht
    aankoop = Gekocht.query.filter_by(userid=userid, goodid=goodid).first()
    if not aankoop:
        flash('Je kunt alleen een review schrijven voor een gekochte reis.', 'danger')
        return redirect(url_for('main.gekocht'))

    # Controleer of er al een review bestaat voor deze gebruiker en reis
    bestaande_review = Feedback.query.filter_by(userid=userid, targetgoodid=goodid).first()
    if bestaande_review:
        flash('Je hebt al een review geschreven voor deze reis.', 'warning')
        return redirect(url_for('main.gekocht'))

    # Voeg een nieuwe review toe aan de database
    new_feedback = Feedback(
        feedbackid=str(uuid.uuid4()),  # Genereer een unieke ID
        userid=userid,
        targetgoodid=goodid,
        rating=int(rating),
        comment=review_text,
        createdat=datetime.datetime.utcnow()
    )
    db.session.add(new_feedback)
    db.session.commit()

    flash('Review succesvol ingediend!', 'success')
    return redirect(url_for('main.review_bedanking'))

@main.route('/review_bedanking', methods=['GET'])
def review_bedanking():
    return render_template('reviewbedanking.html')

@main.route('/api/travels', methods=['GET'])
def get_user_travels():
    if 'userid' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = Users.query.get(session['userid'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    travels = DigitalGoods.query.filter_by(userid=user.userid).all()
    return jsonify([
        {
            'titleofitinerary': t.titleofitinerary,
            'descriptionofitinerary': t.descriptionofitinerary,
            'latitude': t.latitude,
            'longitude': t.longitude,
        } for t in travels
    ])


@main.route('/profile', methods=['GET'])
def profile():
    if 'userid' not in session:
        return redirect(url_for('main.login'))  # Verwijs naar login als gebruiker niet is ingelogd

    # Haal de ingelogde gebruiker op
    user = Users.query.get(session['userid'])
    if not user:
        return redirect(url_for('main.logout'))  # Log uit als de gebruiker niet bestaat

    # Haal de geüploade reizen van de gebruiker op
    reizen = DigitalGoods.query.filter_by(userid=user.userid).all()

    # Render de profielpagina met de gebruiker en reizen
    return render_template('profile.html', user=user, reizen=reizen)

@main.route('/user/<userid>', methods=['GET'])
def user_profile(userid):
    # Zoek de gebruiker op basis van de opgegeven userid
    user = Users.query.get(userid)
    if not user:
        flash("Gebruiker niet gevonden.", "error")
        return redirect(url_for('main.index'))

    # Haal de huidige ingelogde gebruiker op
    current_user_id = session.get('userid')
    if not current_user_id:
        flash("Je moet ingelogd zijn om een profiel te bekijken.", "error")
        return redirect(url_for('main.login'))

    # Controleer of de ingelogde gebruiker deze gebruiker volgt
    is_following = Connections.query.filter_by(
        follower_id=current_user_id, 
        followed_id=user.userid
    ).first() is not None

    # Haal de geüploade reizen van deze gebruiker op
    reizen = DigitalGoods.query.filter_by(userid=user.userid).all()

    # Render de profielpagina met de gegevens van de gebruiker, reizen en volgstatus
    return render_template(
        'profile.html', 
        user=user, 
        reizen=reizen, 
        is_following=is_following
    )

@main.route('/boost_reis', methods=['POST'])
def boost_reis():
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    goodid = request.form.get('goodid')
    reis = DigitalGoods.query.filter_by(goodid=goodid, userid=session['userid']).first()

    if reis:
        # Redirect naar de betaalpagina voor het boosten
        return redirect(url_for('main.boost_payment', goodid=goodid))
    else:
        flash('Reis niet gevonden of u heeft geen rechten om deze reis te boosten.', 'error')
        return redirect(url_for('main.gepost'))

@main.route('/boost_payment/<goodid>', methods=['GET', 'POST'])
def boost_payment(goodid):
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    reis = DigitalGoods.query.filter_by(goodid=goodid, userid=session['userid']).first()

    if not reis:
        flash('Reis niet gevonden of u heeft geen rechten om deze reis te boosten.', 'error')
        return redirect(url_for('main.gepost'))

    if request.method == 'POST':
        # Simuleer een succesvolle betaling (voeg hier een echte betaalprovider-integratie toe)
        payment_success = True

        if payment_success:
            # Update de timestamp om de reis als geboost te markeren
            reis.createdat = datetime.datetime.utcnow()
            db.session.commit()
            flash(f'Reis "{reis.titleofitinerary}" is succesvol geboost!', 'success')
            return redirect(url_for('main.boost_confirm', goodid=goodid))
        else:
            flash('Betaling mislukt. Probeer het opnieuw.', 'error')
            return redirect(url_for('main.boost_payment', goodid=goodid))

    # Render de betaalpagina
    return render_template('boost_payment.html', reis=reis)

@main.route('/boost_confirm/<goodid>', methods=['GET'])
def boost_confirm(goodid):
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    reis = DigitalGoods.query.filter_by(goodid=goodid, userid=session['userid']).first()

    if not reis:
        flash('Reis niet gevonden.', 'error')
        return redirect(url_for('main.gepost'))

    return render_template('boost_confirm.html', reis=reis)


@main.route('/connecties', methods=['GET', 'POST'])
def connecties():
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    user = Users.query.get(session['userid'])

    if not user:
        return redirect(url_for('main.logout'))

    # Volgers ophalen
    followers = Users.query.join(Connections, Connections.follower_id == Users.userid).filter(Connections.followed_id == user.userid).all()

    # Gevolgden ophalen
    following = Users.query.join(Connections, Connections.followed_id == Users.userid).filter(Connections.follower_id == user.userid).all()

    return render_template('connecties.html', user=user, followers=followers, following=following)

@main.route('/zoekconnecties', methods=['GET'])
def zoekconnecties():
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    search_term = request.args.get('search', '').strip()
    current_user_id = session['userid']

    # Zoek gebruikers, sluit de ingelogde gebruiker uit
    query = Users.query.filter(Users.userid != current_user_id)
    if search_term:
        query = query.filter(
            (Users.firstname.ilike(f"%{search_term}%")) |
            (Users.lastname.ilike(f"%{search_term}%"))
        )

    # Haal gebruikers op
    users = query.all()

    # Markeer welke gebruikers gevolgd worden door de huidige gebruiker
    following_ids = {conn.followed_id for conn in Connections.query.filter_by(follower_id=current_user_id).all()}
    for user in users:
        user.is_followed = user.userid in following_ids

    return render_template('zoekconnecties.html', user=Users.query.get(current_user_id), users=users)

@main.route('/toggle_follow', methods=['POST'])
def toggle_follow():
    if 'userid' not in session:
        return redirect(url_for('main.login'))
    
    user = Users.query.get(session['userid'])

    follower_id = session['userid']
    followed_id = request.form.get('followed_id')

    if not followed_id or follower_id == followed_id:
        flash("Ongeldige actie.", "danger")
        return redirect(url_for('main.index'))

    # Zoek naar bestaande verbinding
    connection = Connections.query.filter_by(follower_id=follower_id, followed_id=followed_id).first()

    if connection:
        # Ontvolgen
        db.session.delete(connection)
        db.session.commit()
        flash("Je hebt de gebruiker ontvolgd.", "success")
    else:
        # Volgen
        new_connection = Connections(follower_id=follower_id, followed_id=followed_id)
        db.session.add(new_connection)
        db.session.commit()

        create_notification(
            recipient_id=followed_id,
            sender_id=follower_id,
            message=f" {user.firstname} {user.lastname} volgt je nu!"
        )
        flash("Je volgt de gebruiker nu.", "success")


    # Bepaal de referer-pagina en leid de gebruiker daarheen terug
    referer = request.headers.get('Referer')
    if referer:
        if 'zoekconnecties' in referer:
            return redirect(url_for('main.zoekconnecties'))
        elif 'user' in referer:
            return redirect(url_for('main.user_profile', userid=followed_id))
        elif 'connecties' in referer:
            return redirect(url_for('main.connecties'))
        # Voeg hier extra checks toe voor andere pagina's indien nodig

    # Standaard terugvaloptie
    return redirect(url_for('main.index'))


@main.route('/verkochte_reizen', methods=['GET'])
def verkochte_reizen():
    if 'userid' not in session:
        return redirect(url_for('main.login'))  # Verwijs naar login als gebruiker niet is ingelogd

    user = Users.query.get(session['userid'])  # Haal de huidige gebruiker op
    if not user:
        return redirect(url_for('main.logout'))  # Uitloggen als de gebruiker niet bestaat

    totaal_verdiend = 15  # Start met het welkomstcadeau
    totaal_uitgegeven = 0
    geschiedenis = []

    # Voeg het welkomstcadeau toe aan de geschiedenis
    geschiedenis.append({
        'description': 'Welkomscadeau',
        'amount': 15.0,
        'date': user.createdat or datetime.datetime.utcnow()  # Gebruik de aanmaakdatum van de gebruiker
    })

    # Voeg verkopen toe aan de geschiedenis
    reizen = DigitalGoods.query.filter_by(userid=user.userid).all()
    for reis in reizen:
        aantal_aankopen = Gekocht.query.filter_by(goodid=reis.goodid).count()
        verdiend = aantal_aankopen * reis.price
        totaal_verdiend += verdiend

        if aantal_aankopen > 0:
            for aankoop in Gekocht.query.filter_by(goodid=reis.goodid).all():
                geschiedenis.append({
                    'description': reis.titleofitinerary,
                    'amount': reis.price,
                    'date': aankoop.createdat  # Datum van aankoop
                })

    # Voeg aankopen toe aan de geschiedenis
    gekochte_reizen = Gekocht.query.filter_by(userid=user.userid).all()
    for aankoop in gekochte_reizen:
        reis = DigitalGoods.query.filter_by(goodid=aankoop.goodid).first()
        if reis:
            totaal_uitgegeven += reis.price
            geschiedenis.append({
                'description': reis.titleofitinerary,
                'amount': -reis.price,
                'date': aankoop.createdat  # Datum van aankoop
            })

    # Sorteer de geschiedenis op datum (nieuwste eerst)
    geschiedenis.sort(key=lambda x: x['date'], reverse=True)

    return render_template(
        'reis_aankopen.html',
        totaal_verdiend=totaal_verdiend,
        totaal_uitgegeven=totaal_uitgegeven,
        beschikbaar_saldo=totaal_verdiend - totaal_uitgegeven,
        geschiedenis=geschiedenis,
        user=user
    )

@main.route('/filterpagina', methods=['GET', 'POST'])
def filterpagina():
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    user = Users.query.get(session['userid'])
    if not user:
        return redirect(url_for('main.logout'))

    # Haal filters op uit de sessie
    if 'active_filters' not in session:
        session['active_filters'] = {}

    active_filters = session['active_filters']

    categories = Category.query.all()  # Haal alle beschikbare categorieën op
    available_cities = sorted(set(
        result.start_city.lower() for result in 
        DigitalGoods.query.with_entities(DigitalGoods.start_city).distinct()
        if result.start_city
    ))

    if request.method == 'POST':
        # Haal filters op uit het formulier
        zoekterm = request.form.get('zoekterm', '').strip()
        min_price = request.form.get('min_price', type=float)
        max_price = request.form.get('max_price', type=float)
        city = request.form.get('city', '').strip().lower()
        selected_categories = request.form.getlist('category_id')

        # Sla de filters op in de sessie
        if zoekterm:
            active_filters['zoekterm'] = zoekterm
        if min_price is not None:
            active_filters['min_price'] = min_price
        if max_price is not None:
            active_filters['max_price'] = max_price
        if city:
            active_filters['city'] = city
        if selected_categories:
            active_filters['selected_categories'] = selected_categories

        session.modified = True

    # Bouw query voor gefilterde resultaten
    query = DigitalGoods.query.order_by(DigitalGoods.createdat.desc())

    if 'zoekterm' in active_filters:
        query = query.filter(DigitalGoods.titleofitinerary.ilike(f"%{active_filters['zoekterm']}%"))
    if 'min_price' in active_filters:
        query = query.filter(DigitalGoods.price >= active_filters['min_price'])
    if 'max_price' in active_filters:
        query = query.filter(DigitalGoods.price <= active_filters['max_price'])
    if 'city' in active_filters:
        query = query.filter(DigitalGoods.start_city.ilike(active_filters['city']))
    if 'selected_categories' in active_filters:
        query = query.join(digitalgoods_categories).join(Category).filter(
            Category.categoryid.in_(active_filters['selected_categories'])
        )

    gefilterde_reizen = query.all()

    return render_template(
        'filterpagina.html',
        user=user,
        categories=categories,
        available_cities=available_cities,
        reizen=gefilterde_reizen,
        active_filters=active_filters
    )


@main.context_processor
def inject_user():
    user_id = session.get('userid')
    userx = Users.query.get(user_id) if user_id else None
    return dict(username=userx.firstname if userx else None, userx=userx)

@main.route('/over_ons',methods=['GET'])
def overons():
    return render_template('over_ons.html')

@main.route('/verwijder_filter', methods=['GET'])
def verwijder_filter():
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    # Haal de te verwijderen filter op uit de querystring
    filter_key = request.args.get('filter_key')

    # Maak een kopie van de huidige queryparameters
    query_params = request.args.to_dict()
    query_params.pop('filter_key', None)  # Verwijder het 'filter_key' argument
    query_params.pop(filter_key, None)  # Verwijder de specifieke filter

    # Leid de gebruiker terug naar de searchpagina met bijgewerkte filters
    return redirect(url_for('main.search', **query_params))

@main.route('/messages', methods=['GET', 'POST'])
def messages():
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    current_user_id = session['userid']

    # Haal de ingelogde gebruiker op
    current_user = Users.query.get(current_user_id)

    if request.method == 'POST':
        receiver_id = request.form.get('receiver_id')
        message = request.form.get('message')

        if not receiver_id or not message:
            flash("Selecteer een gebruiker en typ een bericht voordat je verzendt.", "danger")
            return redirect(url_for('main.messages'))

        new_message = Messages(sender_id=current_user_id, receiver_id=receiver_id, message=message)
        db.session.add(new_message)
        db.session.commit()

        create_notification(
            recipient_id=receiver_id,
            sender_id=current_user_id,
            message=f"Gebruiker {current_user.firstname} {current_user.lastname} heeft je een bericht gestuurd."
        )

        return redirect(url_for('main.messages', chat_with=receiver_id))

    # Zoekfunctionaliteit
    search_term = request.args.get('search', '').strip()
    query = Users.query.filter(Users.userid != current_user_id)
    if search_term:
        query = query.filter(
            (Users.firstname.ilike(f"%{search_term}%")) |
            (Users.lastname.ilike(f"%{search_term}%"))
        )

    users = query.all()

    # Ophalen van berichten met geselecteerde gebruiker
    chat_with = request.args.get('chat_with')
    selected_user = None
    messages = []
    if chat_with:
        selected_user = Users.query.filter_by(userid=chat_with).first()
        if selected_user:
            messages = Messages.query.filter(
                (Messages.sender_id == current_user_id) & (Messages.receiver_id == chat_with) |
                (Messages.sender_id == chat_with) & (Messages.receiver_id == current_user_id)
            ).order_by(Messages.created_at).all()
        else:
            flash("Geselecteerde gebruiker bestaat niet.", "danger")

    # Geef 'user' door aan de template
    return render_template(
        'messages.html',
        user=current_user,
        users=users,
        messages=messages,
        chat_with=chat_with,
        selected_user=selected_user
    )


@main.route('/meldingen', methods=['GET'])
def meldingen():
    if 'userid' not in session:
        return redirect(url_for('main.login'))

    current_user_id = session['userid']

    # Haal meldingen op
    alle_meldingen = Meldingen.query.filter_by(recipient_id=current_user_id).order_by(Meldingen.created_at.desc()).all()

    # Markeer als gelezen voor deze sessie
    for melding in alle_meldingen:
        if not melding.is_read:
            melding.is_read = True
            melding.is_recently_read = True  # Tijdelijke indicator
        else:
            melding.is_recently_read = False
    db.session.commit()

    # Zorg ervoor dat de variabele consistent is
    return render_template('meldingen.html', notifications=alle_meldingen)
