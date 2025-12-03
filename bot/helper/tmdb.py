from tmdbv3api import TMDb, Movie, TV
import urllib.parse


tmdb = TMDb()
tmdb.api_key = "68be78e728be4e86e934df1591d26c5b"
tmdb.language = 'en'

def fetch_poster(title: str):
    # Try as movie
    m = Movie()
    movies = m.search(title)
    if movies:
        poster = movies[0].poster_path
        if poster:
            return f"https://image.tmdb.org/t/p/w500{poster}"
    # If no movie result or poster, try as TV show
    tv = TV()
    shows = tv.search(title)
    if shows:
        poster = shows[0].poster_path
        if poster:
            return f"https://image.tmdb.org/t/p/w500{poster}"
    # Fallback: generic placeholder or “not found” image
    return "https://cdn-icons-png.flaticon.com/512/565/565547.png"
