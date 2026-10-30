#!/usr/bin/env python3

import logging 
import sys

import Ice 
import IceStorm

Ice.loadSlice('-I{} spotifice_v3.ice'.format(Ice.getSliceDir()))
import Spotifice # type: ignore # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MediaDirectory")


class MediaDirectoryI(Spotifice.MediaDirectory):
    def __init__(self, communicator):
        self.ic = communicator
        self.properties = communicator.getProperties()
        self.media_servers = []
        self.media_renders = []

    # ----Directory----
    def get_media_servers(self, current=None):
        logger.info(f"get_media_servers: {len(self.media_servers)} servers")
        return self.media_servers
        
    def get_media_renders(self, current=None):
        logger.info(f"get_media_renders: {len(self.media_renders)} renders")
        return self.media_renders
        
    
    # ----AnnounceListener----
    
    def server_up(self, proxy, current=None):
        
        try:
            # Añadir media server
            
            if proxy.ice_isA("::Spotifice::MediaServer"):
                media_server = Spotifice.MediaServerPrx.uncheckedCast(proxy)
                # Verificar si ya existe
                exists = False
                for s in self.media_servers:
                    if s.ice_getIdentity() == proxy.ice_getIdentity():
                        exists = True
                        break
                
                if not exists:
                    self.media_servers.append(media_server)
                    logger.info(f"MediaServer added: {proxy}")
                return
            
            # Añadir render
            media_render = Spotifice.MediaRenderPrx.checkedCast(proxy)
            if proxy.ice_isA("::Spotifice::MediaRender"):
                media_render = Spotifice.MediaRenderPrx.uncheckedCast(proxy)
                # Verificar si ya existe
                exists = False
                for r in self.media_renders:
                    if r.ice_getIdentity() == proxy.ice_getIdentity():
                        exists = True
                        break
                
                if not exists:
                    self.media_renders.append(media_render)
                    logger.info(f"MediaRender added: {proxy}")
                return
                
            logger.warning(f"Unknown proxy type: {proxy}")
        
        except Ice.Exception as e:
            logger.error(f"Error in server up: {e}")
            
    
    def server_down(self, proxy, current=None):
    
        try:
            # Buscar y eliminar de media_servers
            for i, server in enumerate(self.media_servers):
                if server.ice_getIdentity() == proxy.ice_getIdentity():
                    self.media_servers.pop(i)
                    logger.info(f"MediaServer removed: {proxy}")
                    return
            
            # Buscar y eliminar de media_renders
            for i, render in enumerate(self.media_renders):
                if render.ice_getIdentity() == proxy.ice_getIdentity():
                    self.media_renders.pop(i)
                    logger.info(f"MediaRender removed: {proxy}")
                    return
                    
            logger.warning(f"Proxy not found: {proxy}")
            
        except Ice.Exception as e:
            logger.error(f"Error in server_down: {e}")
            
    
    def get_topic_manager(self):
        # Obtener TopicManager
        key = 'IceStorm.TopicManager.Proxy'
        proxy = self.ic.propertyToProxy(key)
        
        if proxy is None:
            logger.error(f"Property '{key}' not set in configuration")
            return None
        
        logger.info(f"Using IceStorm at: {proxy}")
        return IceStorm.TopicManagerPrx.checkedCast(proxy)
        
    # Suscribirse al canal Discovery
    def setup_icestorm(self, adapter):
        try: 
            topic_manager = self.get_topic_manager()
            
            if not topic_manager:
                logger.warning("IceStorm TopicManager not available")
                    
                    
            # Obtener o crear el topic
            topic_name = self.properties.getPropertyWithDefault("Discovery.TopicName", "DiscoveryTopic")
            try:
                self.topic = topic_manager.create(topic_name)
                logger.info(f"Created new topic: {topic_name}")
            except IceStorm.TopicExists:
                self.topic = topic_manager.retrieve(topic_name)
                logger.info(f"Retrieved existing topic: {topic_name}")

                
            # Crear proxy del directory
            directory_prx = adapter.addWithUUID(self)  
            subscriber = Spotifice.AnnounceListenerPrx.uncheckedCast(directory_prx)
                
            # Suscribirse al topic
            self.topic.subscribeAndGetPublisher({}, subscriber)
            logger.info(f"Subscribed to {topic_name}")
                
            
            
        except Exception as e:
            logger.error(f"Error subscribing to IceStorm: {e}")
        
        
def main(ic):
    properties = ic.getProperties()
    directory = MediaDirectoryI(ic)
    
    adapter = ic.createObjectAdapter("MediaDirectoryAdapter")
    proxy = adapter.add(directory, ic.stringToIdentity("mediaDirectory"))
    logger.info(f"MediaDirectory: {proxy}")
    
    # Configurar IceStorm
    directory.setup_icestorm(adapter)
    
    adapter.activate()
    ic.waitForShutdown()
    
    logger.info("Shutdown")
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: media_directory.py <config-file>")
    
    try:
        with Ice.initialize(sys.argv[1]) as communicator:
            main(communicator)
    except KeyboardInterrupt:
        logger.info("Server interrupted by user.")