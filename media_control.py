#!/usr/bin/env python3

import sys
from time import sleep

import Ice
import IceStorm

Ice.loadSlice('-I{} spotifice_v3.ice'.format(Ice.getSliceDir()))
import Spotifice  # type: ignore # noqa: E402

# Version 3
# ----MediaFinderListener----
class MediaFinderListenerI(Spotifice.MediaFinderListener):
        
    def track_found(self, track_info, media_server, current=None):
        print(f"Track found: '{track_info.title}' on server")
        
    def playlist_found(self, playlist, media_server, current=None):
        print(f"Playlist found: '{playlist.name}' on server")

def get_proxy(ic, property, cls):
    proxy = ic.propertyToProxy(property)

    for _ in range(5):
        try:
            proxy.ice_ping()
            break
        except Ice.ConnectionRefusedException:
            sleep(0.5)

    object = cls.checkedCast(proxy)
    if object is None:
        raise RuntimeError(f'Invalid proxy for {property}')

    return object


def main(ic):
    server = get_proxy(ic, 'MediaServer.Proxy', Spotifice.MediaServerPrx)
    render = get_proxy(ic, 'MediaRender.Proxy', Spotifice.MediaRenderPrx)
    
    try:
        session = server.authenticate(render, "user", "secret")
        print(f"Authentication successful for user 'user'")
    except Spotifice.AuthError as e:
        print(f"Authentication failed: {e.reason}")
        sys.exit(1)

    print(f"PRUEBAS NORMALES")
    print("Fetching all tracks...")
    tracks = server.get_all_tracks()
    for t in tracks:
        print(f"- {t.title}")

    print("\nFetching all playlists...")
    playlists = server.get_all_playlists()
    for p in playlists:
        print(f"- {p.name} (ID: {p.id})")

    if not tracks:
        print("No tracks found.")
        return

    

    render.bind_media_server(server,session)
    render.stop()
    
    playlist = playlists[0]
    print(f"\nLoading playlist: {playlist.name}")
    print(f"Playlist ID: {playlist.id}")
    print(f"Number of tracks: {len(playlist.track_ids)}")
        
    render.load_playlist(playlist.id)
        
    # Mostrar estado inicial
    status = render.get_status()
    current_track = render.get_current_track()
    print(f"\nInitial status:")
    print(f"- State: {status.state}")
    print(f"- Current track: {current_track.title}")
    print(f"- Repeat: {status.repeat}")

    print("\n1. Playing first track...")
    render.play()
    sleep(3)  # Play first track for 3 seconds

    print("\n2. Moving to NEXT track...")
    render.next()
    status = render.get_status()
    current_track = render.get_current_track()
    print(f"- New track: {current_track.title}")
    print(f"- State: {status.state}")
    sleep(3)  # Play second track for 3 seconds

    print("\n3. Moving to NEXT track...")
    render.next()
    status = render.get_status()
    current_track = render.get_current_track()
    print(f"- New track: {current_track.title}")
    print(f"- State: {status.state}")
    sleep(3)  # Play third track for 3 seconds

    print("\n4. Moving to PREVIOUS track...")
    render.previous()
    status = render.get_status()
    current_track = render.get_current_track()
    print(f"- Back to track: {current_track.title}")
    print(f"- State: {status.state}")
    sleep(3)  # Play previous track for 3 seconds    
    
    new_playlist = playlists[1]
    print(f"\nLoading NEW playlist: {new_playlist.name}")
    print(f"New Playlist ID: {new_playlist.id}")
    print(f"Number of tracks: {len(new_playlist.track_ids)}")
        
    render.load_playlist(new_playlist.id)
        
    status = render.get_status()
    current_track = render.get_current_track()
    print(f"\nNew playlist status:")
    print(f"- State: {status.state}")
    print(f"- Current track: {current_track.title}")
    print(f"- Repeat: {status.repeat}")

    print("\n5. Playing first track of NEW playlist...")
    render.play()
    sleep(2)

    print("\n6. Moving to PREVIOUS track (Historic was reset)...")
    render.previous()  # Esto no debería hacer nada
    status = render.get_status()
    current_track = render.get_current_track()
    print(f"- Current track after previous: {current_track.title}")
    print(f"- State: {status.state}")

    print("\n7. Moving to NEXT track in playlist...")
    render.next()
    status = render.get_status()
    current_track = render.get_current_track()
    print(f"- New track: {current_track.title}")
    print(f"- State: {status.state}")
    sleep(2)

    print("\n8. Moving to PREVIOUS ...")
    render.previous()
    status = render.get_status()
    current_track = render.get_current_track()
    print(f"- Back to track: {current_track.title}")
    print(f"- State: {status.state}")
    sleep(5)
    
    print("\n9. Pause track ...")
    render.pause()
    status = render.get_status()
    current_track = render.get_current_track()
    print(f" Track {current_track.title} paused...")
    print(f" State: {status.state}")
    sleep(5)
    
    print("\n10. Playing track ...")
    render.play()
    status = render.get_status()
    current_track = render.get_current_track()
    print(f"Track {current_track.title} playing...")
    print(f"State: {status.state}")
    sleep(5)
    
    print("\n11. Stopping track ...")
    render.stop()
    status = render.get_status()
    current_track = render.get_current_track()
    print(f"Track {current_track.title} stopped...")
    print(f"State: {status.state}")
    sleep(5)
    
    print("\n10. Playing track ...")
    render.play()
    status = render.get_status()
    current_track = render.get_current_track()
    print(f"Track {current_track.title} playing...")
    print(f"State: {status.state}")
    
    
    
    
    

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit("Usage: media_control.py <config-file>")

    with Ice.initialize(sys.argv[1]) as communicator:
        main(communicator)