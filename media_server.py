#!/usr/bin/env python3

import logging
import sys
from pathlib import Path

import Ice
import IceStorm
from Ice import identityToString as id2str

import json
from datetime import datetime
import hashlib

Ice.loadSlice('-I{} spotifice_v3.ice'.format(Ice.getSliceDir()))
import Spotifice  # type: ignore # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MediaServer")


class StreamedFile:
    def __init__(self, track_info, media_dir):
        self.track = track_info
        filepath = media_dir / track_info.filename

        try:
            self.file = open(filepath, 'rb')
        except Exception as e:
            raise Spotifice.IOError(track_info.filename, f"Error opening media file: {e}")

    def read(self, size):
        return self.file.read(size)

    def close(self):
        try:
            if self.file:
                self.file.close()
        except Exception as e:
            logger.error(f"Error closing file for track '{self.track.id}': {e}")

    def __repr__(self):
        return f"<StreamState '{self.track.id}'>"


class MediaServerI(Spotifice.MediaServer):
    def __init__(self, media_dir, playlist_dir, users_file, communicator):
        self.media_dir = Path(media_dir)
        self.tracks = {}
        self.playlist_dir = Path(playlist_dir)
        self.playlists = {}
        self.users_file = users_file
        self.users = {}
        self.active_streams = {}  
        self.sessions = {}
        self.ic = communicator
        self.properties = communicator.getProperties()
        self.load_media()
        self.load_playlists()
        self.load_users()
        

    def ensure_track_exists(self, track_id):
        if track_id not in self.tracks:
            raise Spotifice.TrackError(track_id, "Track not found")

    def load_media(self):
        for filepath in sorted(Path(self.media_dir).iterdir()):
            if not filepath.is_file() or filepath.suffix.lower() != ".mp3":
                continue

            self.tracks[filepath.name] = self.track_info(filepath)

        logger.info(f"Load media:  {len(self.tracks)} tracks")
        
    def verify_password(self, username, password):
    
        if username not in self.users:
            return False
       
        user_data = self.users[username]
        salt = user_data["salt"]
        digest = user_data["digest"]
        
        
        password_digest = hashlib.md5(f"{password}{salt}".encode()).hexdigest()
        
        return password_digest == digest
                
        
    

    # Version 1
    def load_playlists(self):
        for filepath in sorted(Path(self.playlist_dir).iterdir()):
            if not filepath.is_file() or filepath.suffix.lower() != ".playlist":
                continue

            playlist = self.playlist_info(filepath)
            self.playlists[playlist.id] = playlist
            
              
        logger.info(f"Load media: {len(self.playlists)} playlists")

    # Version 1
    @staticmethod
    def playlist_info(filepath):
        with open(filepath,'r') as f:
                 data = json.load(f)

        date = data.get('created_at',0)
        
        day, month, year = date.split('-')
        dt = datetime(int(year), int(month), int(day))
        
        date = int(dt.timestamp())

        return Spotifice.Playlist(
            id=data['id'],
            name=data['name'],
            description=data.get('description',''),
            owner=data.get('owner','unknown'),
            created_at=date,
            track_ids=data['track_ids']
        )

    @staticmethod
    def track_info(filepath):
        return  Spotifice.TrackInfo(
            id=filepath.name,
            title=filepath.stem,
            filename=filepath.name)


    def load_users(self):
        
        filepath = Path(self.users_file)

        with open(filepath, 'r') as f:
            data = json.load(f)

        for username, user in data.items():
        
            date_str = user["created_at"]
            
            # Parsear fecha 
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
            created_at = int(dt.timestamp())
            
            self.users[username] = {
                "salt": user["salt"],
                "digest": user["digest"],
                "user_info": Spotifice.UserInfo(
                    username=username,
                    fullname=user["fullname"],
                    email=user["email"],
                    is_premium=user["is_premium"],
                    created_at=created_at
                )
            }


        logger.info(f"Load users: {len(self.users)} users ")
        



    # ---- MusicLibrary ----
    def get_all_tracks(self, current=None):
        return list(self.tracks.values())

    def get_track_info(self, track_id, current=None):
        self.ensure_track_exists(track_id)
        return self.tracks[track_id]
    
    # Version 1            
    # ----PlaylistManager----
    def get_playlist(self,playlist_id,current=None):
        if playlist_id not in self.playlists:
            raise Spotifice.PlaylistError(playlist_id,"Playlist not found")
        return self.playlists[playlist_id]

    def get_all_playlists(self,current=None):
        return list(self.playlists.values())
    
    # Version 2
    # ----AuthManager----
    # Implementacion de authenticate

    def authenticate(self, media_render, username, password, current=None):

        if username not in self.users:
            raise Spotifice.AuthError(username, "User not found")
        
        # Verificar contraseña
        if not self.verify_password(username, password):
            logger.error(f"Invalid password for user: {username}")
            raise Spotifice.AuthError(username, "Invalid password")
            
        logger.info(f"Password verified, creating session...")
        
        user_info = self.users[username]["user_info"]
        
        session_servant = SessionI(user_info, self, self.media_dir)
        prx = current.adapter.addWithUUID(session_servant)
        session_proxy = Spotifice.SecureStreamManagerPrx.checkedCast(prx)
        session_id = session_proxy.ice_getIdentity()
        session_id_str = id2str(session_id)

        self.sessions[session_id_str] = session_servant

        logger.info(f"Session created for user: {username}")
        
        return session_proxy
        
    # Version 3
    # ----MediaFinder----
    
    def find_track(self, track_id, listener, current=None):
    
        # Verificar si esta la pista en el servidor
        if track_id in self.tracks:
            track_info = self.tracks[track_id]
            server_prx = Spotifice.MediaServerPrx.uncheckedCast(current.adapter.createProxy(current.id))
            listener.track_found(track_info, server_prx)
            logger.info(f"Track '{track_id}' found and notified listener")
            
        else:
            logger.info(f"Track '{track_id}' not found in this server")   
            
    def find_playlist(self, playlist_id, listener, current=None):
        
        #Verificar si la playlist existe en el servidor
        
        if playlist_id in self.playlists:
            playlist = self.playlists[playlist_id]
            server_prx = Spotifice.MediaServerPrx.uncheckedCast(current.adapter.createProxy(current.id))
            listener.playlist_found(playlist, server_prx)
            logger.info(f"Playlist '{playlist_id}' found and notified listener")
        else:
            logger.info(f"Playlist '{playlist_id}' not found in this server")


            
    def get_topic_manager(self):
        # Obtener TopicManager
        key = 'IceStorm.TopicManager.Proxy'
        proxy = self.ic.propertyToProxy(key)
        
        if proxy is None:
            logger.error(f"Property '{key}' not set in configuration")
            return None
        
        logger.info(f"Using IceStorm at: {proxy}")
        return IceStorm.TopicManagerPrx.checkedCast(proxy)
            
    def setup_finder(self, adapter):
    
        try:
            topic_manager = self.get_topic_manager()
            
            if not topic_manager:
                logger.warning("IceStorm TopicManager not available")
            
            # Obtener o crear el topic
            topic_name = self.properties.getPropertyWithDefault("Finder.TopicName", "FinderTopic")
            try:
                topic = topic_manager.create(topic_name)
                logger.info(f"Created new topic: {topic_name}")
            except IceStorm.TopicExists:
                topic = topic_manager.retrieve(topic_name)
                logger.info(f"Retrieved existing topic: {topic_name}")
                
            # Suscripcion
            server_prx = adapter.addWithUUID(self)  
            subscriber = Spotifice.MediaFinderPrx.uncheckedCast(server_prx)  
            
            
            topic.subscribeAndGetPublisher({}, subscriber)
            logger.info(f"Subscribed to {topic_name}")
            
        except Exception as e:
            logger.error(f"Error subscribing to IceStorm: {e}")
            
    def setup_discovery(self):
    
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
            
            # Suscribirse al topic
            discovery_publisher = Spotifice.AnnounceListenerPrx.uncheckedCast(discovery_topic.getPublisher())
            
            return discovery_publisher
            
        except Exception as e:
            logger.error(f"Error creating discovery: {e}")     
            return None
            

class SessionI(Spotifice.SecureStreamManager):
    def __init__(self,user_info, media_server, media_dir):
        self.user_info = user_info
        self.media_server = media_server
        self.media_dir = media_dir
        self.active_stream = None
        

    def get_user_info(self, current=None):
        return self.user_info

    def close(self, current=None):

        if self.active_stream:
            self.active_stream.close()
            self.active_stream = None
            
        # Eliminar session
        session_id = id2str(current.id)
        if session_id in self.media_server.sessions:
            del self.media_server.sessions[session_id]
            
        try:
            current.adapter.remove(current.id)
        except Exception as e:
            logger.error(f"Error removing session from adapter: {e}")
            
        
        logger.info(f"Session closed for user: {self.user_info.fullname}")


    def open_stream(self, track_id, current=None):
        
        self.media_server.ensure_track_exists(track_id)

        if self.active_stream:
            self.active_stream.close()

        track_info = self.media_server.tracks[track_id]
        self.active_stream = StreamedFile(track_info, self.media_dir)

        logger.info("Open stream for track: '{}' user: '{}'".format(track_id, self.user_info.fullname))

    def close_stream(self, current=None):
            
        if self.active_stream:
            self.active_stream.close()
            self.active_stream = None
        
        logger.info(f"Closed stream")

    def get_audio_chunk(self, chunk_size, current=None):

        if not self.active_stream:
            raise Spotifice.StreamError("","No open stream")
       
        try:
            data = self.active_stream.read(chunk_size)
            if not data:
                logger.info(f"Track exhausted: '{self.user_info.fullname}'")
                self.close_stream(current)
            return data

        except Exception as e:
            raise Spotifice.IOError(
                self.active_stream.track.filename, f"Error reading file: {e}")




def main(ic):
    properties = ic.getProperties()
    media_dir = properties.getPropertyWithDefault(
        'MediaServer.Content', 'media')
    playlist_dir = properties.getPropertyWithDefault(
         'MediaServer.Playlists','playlists')
    users_file = properties.getPropertyWithDefault(
         'MediaServer.UsersFile','users.json')
    
    
    servant = MediaServerI(Path(media_dir),Path(playlist_dir), Path(users_file), ic)

    adapter = ic.createObjectAdapter("MediaServerAdapter")
    proxy = adapter.add(servant, ic.stringToIdentity("mediaServer1"))
    logger.info(f"MediaServer: {proxy}")
    
    # Suscribirse a Finder
    servant.setup_finder(adapter)
    
    # Anunciar servidor
    discovery_publisher = servant.setup_discovery()
    discovery_publisher.server_up(proxy)
    logger.info(f"Server announced to DiscoveryTopic")
        
    adapter.activate()
    ic.waitForShutdown()

    discovery_publisher.server_down(proxy)
    logger.info("Shutdown")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: media_server.py <config-file>")

    try:
        with Ice.initialize(sys.argv[1]) as communicator:
            main(communicator)
    except KeyboardInterrupt:
        logger.info("Server interrupted by user.")