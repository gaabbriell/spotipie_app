from flask import Flask, render_template, url_for, request, session, redirect
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from flask_sqlalchemy import SQLAlchemy
import time
import matplotlib.pyplot as plt
import os


app = Flask(__name__)

app.secret_key = '3956018761c226359290b1a1edaaa33c'
app.config['SESSION_COOKIE_NAME'] = 'Bobby Wardel Sandimanie III'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///TopArtists.sqlite'

db = SQLAlchemy(app)
app.app_context().push()


CLIENT_ID = '59c4853d23ce43d9b53414136c34fd5c'
CLIENT_SECRET = 'c741ecebc8a24b4991a51cde2bdb36d4'
REDIRECT_URI = 'http://localhost:5000/redirect'
SCOPE = 'user-library-read user-top-read'

# ბაზის შექმნა
class ArtistInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    artist_names = db.Column(db.String(30))
    genres = db.Column(db.String)
    image_url = db.Column(db.String) 

    def __str__(self):
        return f'<ArtistInfo id={self.id} name={self.artist_names} genres={self.genres} image_url={self.image_url}>'



# ავტორიზაციის url იქმენბა რათა მოხდეს spotifyს სერვერთან კავშირი
class AuthorizeURL:
    def __init__ (self, client_id, client_secret, redirect_uri, scope):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope

        self.sp_oauth = self.create_spotify_oauth()
        self.token_info = None

    def create_spotify_oauth(self):
        return SpotifyOAuth(
            client_id= self.client_id,
            client_secret= self.client_secret,
            redirect_uri= self.redirect_uri,
            scope= self.scope
        )
    
    def get_authorize_url(self):
        return self.sp_oauth.get_authorize_url()
    
    # ეს ფუნქცია ავტორიზაციის კოდს იღებს, ამ კოდიდან იღებს ტოკენის ინფორმაციას და სესიაში წერს (ტოკენის ინფოში წერია არტისტებზე ინფორმაცია)
    def set_token_info(self, code): 
        # code - არის ავტორიზაციის კოდი, რომელსაც ვიღებთ მაშინ, როცა redirect page- ზე შემოდის მომხამარებელი.(როცა უკვე დაეთანხმებიან აქაუნთზე წვდომას)
        self.token_info = self.sp_oauth.get_access_token(code) # ამ კოდს ვცვლით access tookesn- ში და ვიღებთ ამ ტოკენს 
        session['token_info'] = self.token_info # ვინახავთ ტოკენს სესიაში
        # print(self.token_info) 

    # ფუნქცია, რომელიც ამოწმებს ტოკენის ვალიდურობას და თუ ვადაგასულია ანახლებს მას.
    def get_token(self):
        if not self.token_info:
            raise Exception('Token not found')
        
        now = int(time.time())
        is_expired = self.token_info['expires_at'] < now

        if is_expired:
            self.token_info = self.sp_oauth.refresh_access_token(self.token_info['refresh_token'])
            return self.token_info
        
        return self.token_info
        

# TopArtist კლასს მოაქვს AuthorizeURL დან ინფორმაცია.
class TopArtist(AuthorizeURL):
    def __init__(self, client_id, client_secret, redirect_uri, scope):
        super().__init__(client_id, client_secret, redirect_uri, scope)

# ფუნქციას მოაქვს მომხამრებლის მიერ 10 ყველაზ ემეტად მოსმენადი არტისტი
    def get_top_artists(self):
        token_info = self.get_token() # ეგრევე ამ ფუნქციას მივმართავთ რადგან მოვიდეს განახლებული ტოკენი.
        sp = spotipy.Spotify(auth=token_info['access_token'])
        top_artists = sp.current_user_top_artists(time_range='long_term', limit=10, offset=0)['items']
        # print(top_artists)

        artist_data = []
        for i in top_artists:
            artist_names = i['name']
            genres  = i['genres']
            genres_str = ', '.join(genres) # genre - ში ბევრი ინფორმაცია ერთადაა ერთ ლისტში მძიმით გამოყოფილი. ამიტომ სტრინგად გარდავქმნით რომ წაიღოს ბაზაში
            image_url = i['images'][0]['url']

            artist_info = ArtistInfo(artist_names= artist_names, genres= genres_str, image_url=image_url)
            db.session.add(artist_info)
            artist_data.append(artist_info)

        db.session.commit()
        return artist_data
    

# ეს კლასი უზრუნველყოფს ჟანრების დათვლას, რათა შექმნას pie chart.
class GenreCounter:
    def __init__(self, artists):
        self.artists = artists
        self.genre_counter = {}

    def count_genres(self):
        for artist in self.artists:
            # ბაზიდან წამოსული ინფორმაცია მოდის ერთ სტრინგად მძიმით გამოყოფილი, ამიტომ ვსპლიტავთ და ლისტში ვათვსებთ.
            genres = artist['genres'].split(', ')
            # print(genres)
            for i in genres:
                if i in self.genre_counter:
                    self.genre_counter[i] += 1 # თუ i დაემთხვევა იმ ჟანრას რაც უკვე არის მაშინ დაემატება.
                else:
                    self.genre_counter[i] = 1 # სხვა შემთხვევაში იქნება 1ის ტოლი.
    
# კლასი უზრუნველყოფს pie chart შექმნას
    def generate_piechart(self):
        labels = list(self.genre_counter.keys()) # რადგან დიქშენერიში გვაქვს, key ანუ ჟანრების დასახელება
        sizes = list(self.genre_counter.values()) # და value მისი რაოდენობა, რომელიც ზემოთ დავითვალეთ.

        fig, ax = plt.subplots(figsize=(6, 6))
        wedges, texts, autotexts = ax.pie(sizes, autopct='%1.1f%%',
                                        textprops=dict(color="w"))
        ax.axis('equal')
        ax.set_facecolor('none')  
        plt.legend(wedges, labels, title="Genres", loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3)
        plt.subplots_adjust(bottom=0.3)

        chart_filename = 'pie_chart.png'
        chart_path = os.path.join(app.static_folder, chart_filename)
        plt.savefig(chart_path, transparent=True)

        return chart_filename
    
# ობიექტი, რომელსაც გადაეცემა ის მონაცემები რაც საჭიროა ინფრმაციის მისაღებად   
artist_info = TopArtist(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SCOPE)

# პირველი route სადაც ხდება ავტორიზაციის ლინკზე მიმართვა
@app.route('/')
def login():
    auth_url = artist_info.get_authorize_url()
    return redirect(auth_url)
    
# redirect route სადაც ავოტრიზაციის შემდეგ გადმომისამართდება მომხამრებელი
@app.route('/redirect')
def redirectPage():
    session.clear()
    code = request.args.get('code')
    if code:
        artist_info.set_token_info(code)

        # ჯერ ვშლით ინფორმაციას ბაზიდან, რათა ყოველ შესვლაზე იყოს განახლებადი.
        db.session.query(ArtistInfo).delete()
        db.session.commit()
        artist_data = artist_info.get_top_artists()


        artists = ArtistInfo.query.all()  # მოგვაქვს ინფორმაცია ბაზიდან

        artists_list = []
        for artist in artists:
            artist_data = {
                'name': artist.artist_names,
                'genres': artist.genres,
                'image': artist.image_url if artist.image_url else None
            }
            artists_list.append(artist_data)

        genre_counter = GenreCounter(artists_list)
        genre_counter.count_genres()
        chart_filename = genre_counter.generate_piechart()

        return render_template('artists.html', artists=artists_list, chart_filename=chart_filename)
    else:
        return redirect(url_for('login'))
    
if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)