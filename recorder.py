# Imports für die Wiedergabe
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from time import sleep

# Imports für die Aufzeichnung
from pydub import AudioSegment
import os
import soundcard as sc
import scipy.io.wavfile as wavf

# Imports für die MP3 Tags inkl. Cover-Art
from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TALB, TPE1, TRCK, APIC
import requests
import shutil

from dotenv import load_dotenv

load_dotenv() 


def init_spotipy():
    #scope = "user-read-playback-state,user-modify-playback-state"
    scope = "user-read-playback-state"
    print("\n\nStelle spotpy Client-Verbindung her.")
    return spotipy.Spotify(client_credentials_manager=SpotifyOAuth(scope=scope))


def get_my_playlist(sp):
    # Suche nach der Playlist "Kassettenrekorder" (Muss dem Profil zugewiesen sein)
    playlist = None
    playlists = sp.current_user_playlists()
    while playlists:
        for i, pl in enumerate(playlists['items']):
            if pl['name'] == "Kassettenrekorder":
                playlist = pl['uri']
            #print("%4d %s %s" % (i + 1 + playlists['offset'], pl['uri'],  pl['name']))
        if playlists['next']:
            playlists = sp.next(playlists)
        else:
            playlists = None

    if playlist == None:
        print("Keine Playlist mit dem Namen \"Kassettenrekorder\" gefunden!")
    else:
        print(f"Playlist mit dem Namen \"Kassettenrekorder\" gefunden: {playlist}")
    return playlist


def get_local_playback_device(sp):
    # Wiedergabegerät für Spotify auf den aktuellen Computer festlegen
    device_id = None
    res = sp.devices()
    # pprint(res)
    for device in res['devices']:
        if device['type'] == "Computer":
            device_id = device['id']
            print("Die Spotify-Wiedergabe wird auf die device-id {0} (Computer) gelenkt.".format(device_id))
    return device_id


def set_volume(sp, volume, device_id):
    # Um die Lautstärke setzen zu können, muss eine Wiedergabe laufen / gerade gelaufen sein
    print(f'Setze die Spotify-Lautstärke auf {volume}.')
    sp.start_playback(device_id=device_id, uris=['spotify:track:6gdLoMygLsgktydTQ71b15'])
    sp.volume(volume)
    sleep(3)
    sp.pause_playback(device_id=device_id)


def list_record_devices():
    mics = sc.all_microphones(include_loopback=True)
    print("\nInput devices found:")
    for i in range(len(mics)):
        try:
            print(f"{i}: {mics[i].name}")
        except Exception as e:
            print(e)
    

def recorder(sp, volume, samplerate):
    device_id = get_local_playback_device(sp)
    set_volume(sp, volume, device_id)
    
    # list_record_devices()
    mics = sc.all_microphones(include_loopback=True)
    default_mic = mics[0]
    print(f"Für die Aufnahme wird das Gerät {default_mic} genutzt.")
    print("Für die Wiedergabe am Computer bitte das gleiche Gerät auswählen...")

    sp_playlist = sp.playlist_tracks(playlist_id=get_my_playlist(sp))
    for track in sp_playlist['items']:
        # print(json.dumps(track, indent=4))
        track_id = track['track']['id']
        track_artist = track['track']['album']['artists'][0]['name']
        track_image = track['track']['album']['images'][0]['url']
        track_album= track['track']['album']['name']
        track_name = track['track']['name']
        track_number = track['track']['track_number']
        track_duration_ms = track['track']['duration_ms']
        print(f"\nAktueller Titel: {track_name} von {track_artist} aus dem Album {track_album} ({track_duration_ms/1000:.2f} Sekunden), Coverbild: {track_image}")
        
        sp.start_playback(device_id=device_id, uris=['spotify:track:{0}'.format(track_id)])
        # track_duration_ms=3000
        with default_mic.recorder(samplerate=samplerate) as mic: 
            print(f"Recording startet auf {default_mic}")
            data = mic.record(numframes=int(samplerate*track_duration_ms/1000))
            
        print("Recording beendet, speichere WAV-Datei...")
        tmpfile = os.path.join(os.getcwd(), 'out.wav')
        wavf.write(tmpfile, samplerate, (data * 32767).clip(-32768, 32767).astype('int16')) # aufgezeichnet wird ein 32 bit float Array, wir wollen ein 16 Bit Integer PCM

        mp3file = os.path.join(os.getcwd(), f'{track_number:02d} {track_name}.mp3')
        print(f'Konvertiere als MP3 und speichere als {mp3file}.')
        sound = AudioSegment.from_wav(tmpfile)
        sound.export(mp3file, format='mp3')

        print("Schreibe die wichtigsten MP3-Tags")
        # Read the ID3 tag or create one if not present
        try: 
            tags = ID3(mp3file)
        except ID3NoHeaderError:
            print("Adding ID3 header")
            tags = ID3()

        tags["TIT2"] = TIT2(encoding=3, text=track_name)
        tags["TALB"] = TALB(encoding=3, text=track_album)
        tags["TPE1"] = TPE1(encoding=3, text=track_artist)
        tags["TRCK"] = TRCK(encoding=3, text=f'{track_number:02d}')

        # Download des Cover-Bilds
        response = requests.get(track_image, stream=True)
        with open('img.jpg', 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
        del response

        with open('img.jpg', 'rb') as albumart:
            tags['APIC'] = APIC(encoding=3, mime='image/jpeg', type=3, desc=u'Cover', data=albumart.read())     

        tags.save(mp3file)
     
        sleep(1)



recorder(init_spotipy(), 100, 48000)