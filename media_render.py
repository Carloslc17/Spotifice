#!/usr/bin/env python3

import logging
import sys
from contextlib import contextmanager

import Ice
import IceStorm
from Ice import identityToString as id2str

from gst_player import GstPlayer

Ice.loadSlice('-I{} spotifice_v3.ice'.format(Ice.getSliceDir()))
import Spotifice  # type: ignore # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MediaRender")


class MediaRenderI(Spotifice.MediaRender):
    def __init__(self, player):
        self.player = player
        self.server: Spotifice.MediaServerPrx = None
        self.session: Spotifice.SecureStreamManagerPrx = None
        self.current_track = None
        self.current_playlist = None
        self.playlist_tracks = []
        self.current_playlist_index = 0
        self.repeat = False
        self.history = []
        self.paused = False
        self.ic = communicator
        self.properties = communicator.getProperties()
        


    def ensure_player_stopped(self):
    
        if self.player.is_playing():
            raise Spotifice.PlayerError(reason="Already playing")

    def ensure_server_bound(self):
        if not self.server or not self.session:
            raise Spotifice.BadReference(reason="No MediaServer bound or active session")

    # --- RenderConnectivity ---

    def bind_media_server(self, media_server, stream_manager, current=None):
        try:
            media_server.ice_ping()
            stream_manager.ice_ping()
        except Ice.ConnectionRefusedException as e:
            raise Spotifice.BadReference(reason=f"MediaServer not reachable: {e}")

        self.server = media_server
        self.session = stream_manager
        logger.info(f"Bound to MediaServer '{id2str(media_server.ice_getIdentity())}'")

    def unbind_media_server(self, current=None):
        self.stop(current)
        
        if self.session:
            self.session.close()
            self.session = None
        
        self.server = None
        logger.info("Unbound MediaServer, close session")

    # --- ContentManager ---

    def load_track(self, track_id, current=None):
        self.ensure_server_bound()

        try:
            with self.keep_playing_state(current):
                self.current_track = self.server.get_track_info(track_id)
                self.current_playlist = None
                self.playlist_tracks = []

            logger.info(f"Current track set to: {self.current_track.title}")

        except Spotifice.TrackError as e:
            logger.error(f"Error setting track: {e.reason}")
            raise

    def get_current_track(self, current=None):
        return self.current_track
    
    # Version 1
    def load_playlist(self, playlist_id, current=None):
        self.ensure_server_bound()
        
        try: 
        
            if self.player.is_playing() or self.paused:
                self.stop(current)
               
            self.current_playlist = self.server.get_playlist(playlist_id)

            # Obtener todas las pistas de la playlist
            self.playlist_tracks = []
            for track_id in self.current_playlist.track_ids:
                track = self.server.get_track_info(track_id)
                self.playlist_tracks.append(track)

            # Actualiza la pista actual a la primera pista de la playlist
            # Borrar historico al cargar nueva playlist
            self.current_track = self.playlist_tracks[0]
            self.history = []
            self.current_playlist_index = 0

            logger.info(f"Current playlist set to: {self.current_playlist.name}")

        except Spotifice.PlaylistError as e:
            logger.error(f"Error setting playlist: {e.reason}")
            raise
        except Spotifice.TrackError as e:
            logger.error(f"Error loading track: {e.reason}")
            raise
        

    # --- PlaybackController ---

    @contextmanager
    def keep_playing_state(self, current):
        playing = self.player.is_playing()
        if playing:
            self.stop(current)
        try:
            yield
        finally:
            if playing:
                self.play(current)

    def play(self, current=None):
    
        # Version 1
        if self.paused:
            try:
                self.player.resume() 
                self.paused = False
                logger.info("Playback resumed from pause")
                return 
            except Exception as e:  
                logger.error(f"Failed to resume: {e}")
                raise Spotifice.PlayerError(reason="Failed to resume playback")
    
        def get_chunk_hook(chunk_size):
            try:
                return self.session.get_audio_chunk(chunk_size)
            except Spotifice.IOError as e:
                logger.error(e)
            except Ice.Exception as e:
                logger.critical(e)

        assert current, "remote invocation required"

        self.ensure_player_stopped()
        self.ensure_server_bound()

        if not self.current_track:
            raise Spotifice.TrackError(reason="No track loaded")

        try:
            self.session.open_stream(self.current_track.id)
        except Spotifice.BadIdentity as e:
            logger.error(f"Error starting stream: {e.reason}")
            raise Spotifice.StreamError(reason="Stream setup failed")

        self.player.configure(get_chunk_hook)
        if not self.player.confirm_play_starts():
            raise Spotifice.PlayerError(reason="Failed to confirm playback")
            
        

    def stop(self, current=None):
    
        if self.session:
            self.session.close_stream()

        if not self.player.stop():
            raise Spotifice.PlayerError(reason="Failed to confirm stop")

        self.paused = False
        logger.info("Stopped")

    # Version 1
    def pause(self,current=None):
        if not self.player.is_playing():
            raise Spotifice.PlayerError(reason="Not playing")
        try:
        
            self.player.pause()
            self.paused = True
            
        except Exception as e:  
            logger.error(f"Pause failed: {e}")
            raise Spotifice.PlayerError(reason="Failed to pause playback")


        logger.info("Playback paused")

    # Version 1
    def get_status(self,current=None):
        if self.paused:
            state = Spotifice.PlaybackState.PAUSED
        elif self.player.is_playing():
            state = Spotifice.PlaybackState.PLAYING
        else:
            state = Spotifice.PlaybackState.STOPPED

        return Spotifice.PlaybackStatus(
            state = state,
            current_track_id = self.current_track.id,
            repeat = self.repeat
        )
    
    # Version 1
    def next(self,current=None):
      if not self.current_playlist:
          logger.info("No playlist is playing")
          return
      
      if self.current_track:
          self.history.append(self.current_track)
      
      # Pasar a siguiente pista de la playlist
      if self.current_playlist_index + 1 < len(self.playlist_tracks):
          self.current_playlist_index += 1
      elif self.repeat:
          self.current_playlist_index = 0
      else:
          return
      
      self.current_track = self.playlist_tracks[self.current_playlist_index]

      if self.player.is_playing():
          self.stop(current)
          self.play(current)

      logger.info(f"Moving track to next: {self.current_track.title}")


    # Version 1
    def previous(self,current=None):
      if not self.history:
          logger.info("No previous track")
          return
      previous_track = self.history.pop()

      if self.current_playlist and previous_track in self.playlist_tracks:
            self.current_playlist_index = self.playlist_tracks.index(previous_track)
      else:
            
            self.current_playlist = None
            self.playlist_tracks = []

      self.current_track = previous_track   

      if self.player.is_playing():
          self.stop(current)
          self.play(current)

      logger.info(f"Moving to previous track: {self.current_track.title} ")

      

    # Version 1
    def set_repeat(self,value,current=None):
        self.repeat = value
        logger.info(f"Repeat mode set to {value}")
        
        
    def get_topic_manager(self):
        # Obtener TopicManager
        key = 'IceStorm.TopicManager.Proxy'
        proxy = self.ic.propertyToProxy(key)
        
        if proxy is None:
            logger.error(f"Property '{key}' not set in configuration")
            return None
        
        logger.info(f"Using IceStorm at: {proxy}")
        return IceStorm.TopicManagerPrx.checkedCast(proxy)

    # Suscribirse a DiscoveryTopic
    def setup_discovery(self, adapter):
    
        try:
            topic_manager = self.get_topic_manager()
            
            if not topic_manager:
                logger.warning("IceStorm TopicManager not available")
                return None
            
            # Obtener o crear el topic
            topic_name = self.properties.getPropertyWithDefault("Discovery.TopicName", "DiscoveryTopic")
            try:
                discovery_topic = topic_manager.create(topic_name)
                logger.info(f"Created new topic: {topic_name}")
            except IceStorm.TopicExists:
                discovery_topic = topic_manager.retrieve(topic_name)
                logger.info(f"Retrieved existing topic: {topic_name}")
            
            # Obtener publicador
            discovery_publisher = Spotifice.AnnounceListenerPrx.uncheckedCast(discovery_topic.getPublisher())
            
            return discovery_publisher
            
        except Exception as e:
            logger.error(f"Error creating discovery: {e}")
            return None

def main(ic, player):
    servant = MediaRenderI(player)

    adapter = ic.createObjectAdapter("MediaRenderAdapter")
    proxy = adapter.add(servant, ic.stringToIdentity("mediaRender1"))
    logger.info(f"MediaRender: {proxy}")
    
    discovery_publisher = servant.setup_discovery(adapter)
    discovery_publisher.server_up(proxy)
    logger.info(f"Render announced to DiscoveryTopic")

    adapter.activate()
    ic.waitForShutdown()

    discovery_publisher.server_down(proxy)
    logger.info("Shutdown")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: media_render.py <config-file>")

    player = GstPlayer()
    player.start()
    try:
        with Ice.initialize(sys.argv[1]) as communicator:
            main(communicator, player)
    except KeyboardInterrupt:
        logger.info("Server interrupted by user.")
    finally:
        player.shutdown()