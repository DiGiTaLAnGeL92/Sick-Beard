import os.path

import gc
import cgi
import sqlite3
import time

from Cheetah.Template import Template
import cherrypy

from sickbeard import config
from sickbeard import db
from sickbeard import nzb
from sickbeard import processTV
from sickbeard import ui
from sickbeard.tv import *
from lib.tvdb_api import tvdb_exceptions

import sickbeard
import sickbeard.helpers


class TVDBWebUI:
    def __init__(self, config, log):
        self.config = config
        self.log = log

    def selectSeries(self, allSeries):
        
        for curShow in allSeries:
            showObj = sickbeard.helpers.findCertainShow(sickbeard.showList, int(curShow['sid']))
            if showObj != None:
                raise cherrypy.HTTPRedirect("/addShow/?showDir=" + self.config['_showDir'] + "&seriesList=" + curShow['sid'])
        
        searchList = ",".join([x['sid'] for x in allSeries])
        raise cherrypy.HTTPRedirect("/addShow/?showDir=" + self.config['_showDir'] + "&seriesList=" + searchList)


class Whatever:
    
    @cherrypy.expose
    def index(self):
        
        outStr = ""
        
        outStr += """<a href="/displayShowList">Show List</a><br />\n"""
        outStr += """<a href="/addShow">Add Show</a><br />\n"""
        outStr += """<a href="/addRootDir">Add Shows From Root Dir</a><br />\n"""
        outStr += """<a href="/comingEpisodes">Coming Episodes</a><br />\n"""
        outStr += """<a href="/processEpisode">Process Episode</a><br />\n"""
        outStr += """<a href="/editConfig">Config</a><br />\n"""
        outStr += """<a href="/forceBacklog">Force Backlog search</a><br /><br />\n"""
        outStr += """<!--<a href="/restart">Restart</a><br />-->\n"""
        outStr += """<a href="/shutdown">Shutdown</a><br />\n"""
        
        return outStr
    
    @cherrypy.expose
    def shutdown(self):

        threading.Timer(2, sickbeard.saveAndShutdown).start()
        return "Shutting down..."
    
    @cherrypy.expose
    def restart(self):

        threading.Timer(2, sickbeard.restart).start()
        return "Restarting... (wait ~30 seconds)"

    
    @cherrypy.expose
    def forceBacklog(self):

        # force it to run the next time it looks
        sickbeard.backlogSearchScheduler.forceSearch()
        Logger().log("Backlog set to run at the next search iteration")
        
        return "Backlog will run at the next search iteration"
    
    
    @cherrypy.expose
    def addRootDir(self, dir=None):
        
        if dir == None:
            myTemplate = Template(file="data/includes/addRootDir.html")
            return self._munge(myTemplate) 
        
        result = ui.addShowsFromRootDir(dir)

        return self._munge(result)
        
    
    @cherrypy.expose
    def showPoster(self, show=None):
        
        if show == None:
            return "Invalid show" #TODO: make it return a standard image
        else:
            showObj = sickbeard.helpers.findCertainShow(sickbeard.showList, int(show))
            
        if showObj == None:
            return "Unable to find show" #TODO: make it return a standard image
    
        posterFilename = os.path.join(showObj.location, "folder.jpg")
        if os.path.isfile(posterFilename):
            
            posterFile = open(posterFilename, "rb")
            cherrypy.response.headers['Content-type'] = "image/jpeg"
            posterImage = posterFile.read()
            posterFile.close()
            return posterImage
        
        else:
            print "No poster" #TODO: make it return a standard image
    
    @cherrypy.expose
    def displayShowList(self):
        outStr = ""
        
        outStr += "<a href=\"/\">Home</a><br /><br />"

        for show in sickbeard.showList:
            outStr += """<a href="/displayShow/?show={0}">{1}</a><br />\n""".format(show.tvdbid, show.name)
    
        for show in sickbeard.loadingShowList.values():
            outStr += show.name + " (loading)<br />\n"

        outStr += """<br /><a href="/addShow">Add Show</a><br />\n"""
        
        return outStr
    
    @cherrypy.expose
    def createShow(self, showName=None, showID=None, showDir=None):

        if showName != None:
            t = tvdb_api.Tvdb(custom_ui=TVDBWebUI)
            try:
                s = t[showName]
            except tvdb_exceptions.tvdb_shownotfound:
                return "Couldn't find that show"

            # should never get here
            return "Whoops, shouldn't be here"

        myTemplate = Template(file="data/includes/createShow.html")
        myTemplate.resultList = []
        
        if showID != None:
            showIDList = showID.split(",")
            
            if len(showIDList) == 1:
                return "making NFO for show " + showIDList[0] + " and then creating a show for that folder"
            else:
                t = tvdb_api.Tvdb()
                myTemplate.resultList = [t[int(x)] for x in showIDList]
        
        return self._munge(myTemplate)
    
    
    @cherrypy.expose
    def displayShow(self, show=None):
        
        outStr = ""

        outStr += "<a href=\"/\">Home</a><br /><br />"
        
        if show == None:
            return "Invalid show"
        else:
            showObj = sickbeard.helpers.findCertainShow(sickbeard.showList, int(show))
            
            if showObj == None:
                return "Unable to find show"
            
            outStr += "Name: " + showObj.name 
            outStr += " <a href=\"/editShow/?show=" + str(showObj.tvdbid) + "\">(edit)</a>"
            outStr += " <a href=\"/deleteShow/?show=" + str(showObj.tvdbid) + "\">(delete)</a>"
            outStr += " <a href=\"/updateShow/?show=" + str(showObj.tvdbid) + "\">(quick update)</a>"
            outStr += " <a href=\"/refreshDir/?show=" + str(showObj.tvdbid) + "\">(refresh folder)</a>"
            outStr += " <a href=\"/fixEpisodeNames/?show=" + str(showObj.tvdbid) + "\">(fix episode names)</a>"
            outStr += " <a href=\"/updateShow/?show=" + str(showObj.tvdbid) + "&force=1\">(force update - takes forever)</a><br />\n"
            outStr += "Airs: " + showObj.airs + " on " + showObj.network + "<br />\n"
            outStr += "Status: " + showObj.status + "<br />\n"
            try:
                outStr += "Location: " + showObj.location + "<br />\n"
            except NoNFOException:
                outStr += "Location: " + showObj._location + " **<br />n"
            outStr += "Quality: " + qualityStrings[showObj.quality] + "<br />\n"
            outStr += "Predownload: " + str(showObj.predownload) + "<br />\n"
            outStr += "Season Folders: " + str(showObj.seasonfolders) + "<br />\n"
            
            outStr += "<br /><br />"
            
            
            myDB = db.DBConnection()
            myDB.checkDB()

            Logger().log(str(showObj.tvdbid) + ": Displaying all episodes from the database")
        
            sqlResults = []
    
            try:
                sql = "SELECT * FROM tv_episodes WHERE showid = " + str(showObj.tvdbid) + " ORDER BY season, episode ASC"
                Logger().log("SQL: " + sql, DEBUG)
                sqlResults = myDB.connection.execute(sql).fetchall()
            except sqlite3.DatabaseError as e:
                Logger().log("Fatal error executing query '" + sql + "': " + str(e), ERROR)
                raise
    
            curSeason = 0
    
            for epResult in sqlResults:
               
                if int(epResult["season"]) != curSeason:
                    if curSeason != 0:
                        outStr += "</ul><br />\n"
                    outStr += "<b>Season " + str(epResult["season"]) + "</b> " + \
                            "(<a href=\"/setStatus/?show=" + str(showObj.tvdbid) + "&season=" + str(epResult["season"]) + "&status=" + str(BACKLOG) + "\">add to backlog</a>) " + \
                            "(<a href=\"/setStatus/?show=" + str(showObj.tvdbid) + "&season=" + str(epResult["season"]) + "&status=" + str(DISCBACKLOG) + "\">add to disc backlog</a>)<br />\n"
                    outStr += "<ul>\n"
                    curSeason = int(epResult["season"])
                
                outStr += "<li><a href=\"/displayEpisode/?show=" + str(showObj.tvdbid) + "&season=" + str(epResult["season"]) + "&episode=" + str(epResult["episode"]) + "\">"
                outStr += cgi.escape(unicode(showObj.name)).encode('ascii', 'xmlcharrefreplace') + " - " + str(epResult["season"]) + "x" + str(epResult["episode"])
                outStr += " - " + cgi.escape(unicode(epResult["name"])).encode('ascii', 'xmlcharrefreplace') + "</a>"
                outStr += " (" + statusStrings[int(epResult["status"])] + ")"
                outStr += " (<a href=\"/searchEpisode/?show=" + str(showObj.tvdbid) + "&season=" + str(epResult["season"]) + "&episode=" + str(epResult["episode"]) + "\">find NZB</a>)</li>\n"
                
            outStr += "</ul><br /><br />\n"

            return outStr            
            
            seasons = showObj.episodes.keys()
            seasons.sort()
            
            for season in seasons:
                outStr += "Season " + str(season) + "<br />\n"
                outStr += "<ul>\n"
                
                episodes = showObj.episodes[season].keys()
                episodes.sort()
                for episode in episodes:
                    ep = showObj.getEpisode(season, episode)
                    outStr += "<li>" + ep.prettyName() + " (" + statusStrings[ep.status] + ")</li>\n"
                
                outStr += "</ul><br />\n"
            
        return outStr
    
    @cherrypy.expose
    def updateShow(self, show=None, force=0):
        
        if show == None:
            return "Invalid show"
        
        showObj = sickbeard.helpers.findCertainShow(sickbeard.showList, int(show))
        
        if showObj == None:
            return "Unable to find the specified show"
        
        # force the update from the DB
        sickbeard.updateScheduler.updater.updateShowFromTVDB(showObj, bool(force))
        
        #showObj.loadFromTVDB(cache=False)
        #showObj.loadEpisodesFromTVDB(cache=False)
        #showObj.writeEpisodeNFOs()
        #showObj.saveToDB()
        #showObj.flushEpisodes()
        #gc.collect() # try it

        raise cherrypy.HTTPRedirect("/displayShow/?show=" + show)

    @cherrypy.expose
    def deleteShow(self, show=None):

        if show == None:
            return "Invalid show"
        
        showObj = sickbeard.helpers.findCertainShow(sickbeard.showList, int(show))
        
        if showObj == None:
            return "Unable to find the specified show"

        showObj.deleteShow()
        
        return self._munge("Show has been deleted.")


    @cherrypy.expose
    def fixEpisodeNames(self, show=None):
        
        if show == None:
            return "Invalid show"
        
        showObj = sickbeard.helpers.findCertainShow(sickbeard.showList, int(show))
        
        if showObj == None:
            return "Unable to find the specified show"
        
        showObj.fixEpisodeNames()

        raise cherrypy.HTTPRedirect("/displayShow/?show=" + show)
        
    
    @cherrypy.expose
    def refreshDir(self, show=None):
        
        if show == None:
            return "Invalid show"
        
        showObj = sickbeard.helpers.findCertainShow(sickbeard.showList, int(show))
        
        if showObj == None:
            return "Unable to find the specified show"
        
        showObj.refreshDir()

        raise cherrypy.HTTPRedirect("/displayShow/?show=" + show)
        
    
    @cherrypy.expose
    def editShow(self, show=None, location=None, quality=None, predownload=None, seasonfolders=None):
        
        if show == None:
            return "Invalid show"
        
        showObj = sickbeard.helpers.findCertainShow(sickbeard.showList, int(show))
        
        if showObj == None:
            return "Unable to find the specified show"

        if location == None and quality == None and predownload == None and seasonfolders == None:
            
            t = Template(file="data/includes/editShow.html")
            with showObj.lock:
                t.show = showObj
                t.qualityStrings = qualityStrings
                t.qualities = (SD, HD, ANY)
            
            return self._munge(t)
        
        if seasonfolders == "on":
            seasonfolders = 1
        else:
            seasonfolders = 0

        if predownload == "on":
            predownload = 1
        else:
            predownload = 0

        with showObj.lock:

            print "changing quality from", showObj.quality, "to", quality
            showObj.quality = int(quality)
            showObj.predownload = int(predownload)
            showObj.seasonfolders = int(seasonfolders)
                        
            # if we change location clear the db of episodes, change it, write to db, and rescan
            if os.path.isdir(location) and os.path.normpath(showObj._location) != os.path.normpath(location):
                
                #myDB = db.DBConnection()
                #myDB.checkDB()
                
                #Logger().log(str(showObj.tvdbid)+": Refreshing ")
            
                # delete all the episodes that had a file associated with them
                #try:
                #    sql = "DELETE FROM tv_episodes WHERE showid = " + str(showObj.tvdbid) + " AND location != ''"
                #    myDB.connection.execute(sql).fetchall()
                #    myDB.connection.commit()
                #except sqlite3.DatabaseError as e:
                #    Logger().log("Fatal error executing query '"+sql+"': "+str(e), ERROR)
                #    raise

                # get rid of lingering references
                #showObj.flushEpisodes()

                # change it
                showObj.location = location
                
                showObj.refreshDir()
                
                # grab updated info from TVDB
                #showObj.loadEpisodesFromTVDB()

                # rescan the episodes in the new folder
                showObj.loadEpisodesFromDir()
                    
            # save it to the DB
            showObj.saveToDB()
                
            raise cherrypy.HTTPRedirect("/displayShow/?show=" + show)

    @cherrypy.expose
    def addShow(self, showDir=None, showName=None, seriesList=None):
        
        myTemplate = Template(file="data/includes/addShow.html")
        myTemplate.resultList = None
        myTemplate.showDir = showDir
        
        # if no showDir then start at the beginning
        if showDir == None:
            return self._munge(myTemplate)

        # if we have a dir and a name it means we're mid-search, so get our TVDB list and forward them to the selection screen
        if showDir != None and showName != None:
            t = tvdb_api.Tvdb(custom_ui=TVDBWebUI)
            t.config['_showDir'] = urllib.quote_plus(showDir)
            try:
                s = t[showName] # this will throw a cherrypy exception
            except tvdb_exceptions.tvdb_shownotfound:
                return "Couldn't find that show"
    

        showDir = os.path.normpath(urllib.unquote_plus(showDir))

        if seriesList != None:
            showIDs = seriesList.split(",")
        else:
            showIDs = []

        # if we have a folder but no ID specified then we try scanning it for NFO
        if len(showIDs) == 0:


            try:
                #newShowAdder = ui.ShowAdder(showDir)
                sickbeard.showAddScheduler.addShowToQueue(showDir)
            except exceptions.NoNFOException:
                myTemplate.resultList = []
                myTemplate.showDir = urllib.quote_plus(showDir)
                return self._munge(myTemplate)

            #newShowAdder.start()

            # try making a show there. if it fails then make them pick what show to create
            #try:
            #    newShow = TVShow(showDir)
            #except exceptions.MultipleShowObjectsException:
            #    return "That show already exists, can't create a duplicate"
            #except exceptions.NoNFOException:
            #    myTemplate.resultList = []
            #    myTemplate.showDir = urllib.quote_plus(showDir)
            #    return self._munge(myTemplate)

            #newShow.loadEpisodesFromDir()
            #try:
            #    newShow.loadEpisodesFromTVDB()
            #except tvdb_exceptions.tvdb_error as e:
            #    Logger().log("Error with TVDB, not creating episode list: "+str(e), ERROR)
            #newShow.saveToDB()
            #sickbeard.showList.append(newShow)
            
            raise cherrypy.HTTPRedirect("/displayShowList/")
        
        # if we have a single ID then just make a show with that ID
        elif len(showIDs) == 1:
            
            # if the dir doesn't exist then give up
            if not helpers.makeDir(showDir):
                return "Show dir doesn't exist and I'm unable to create it"
    
            # if the folder exists then make the show there
            if not helpers.makeShowNFO(showIDs[0], showDir):
                return "Unable to make tvshow.nfo?"
            
            # just go do the normal show creation now that we have the NFO
            raise cherrypy.HTTPRedirect("/addShow/?showDir=" + urllib.quote_plus(showDir))
        
        # if we have multiple IDs then let them pick
        else:
            
            t = tvdb_api.Tvdb()
            myTemplate.resultList = [t[int(x)] for x in showIDs]
            myTemplate.showDir = urllib.quote_plus(showDir)
            
            return self._munge(myTemplate)

    
    @cherrypy.expose
    def displayEpisode(self, show=None, season=None, episode=None):
        
        epObj = self._getEpisode(show, season, episode)
        
        if isinstance(epObj, str):
            return epObj
        else:
            t = Template(file="data/includes/displayEpisode.html")
            t.episode = epObj
            t.statusStrings = statusStrings
            
        return self._munge(t)

    @cherrypy.expose
    def setStatus(self, show=None, season=None, episode=None, status=None):
        
        if show == None or season == None or status == None:
            return "You must specify a show and season at least"
        
        if not statusStrings.has_key(int(status)):
            return "Invalid status"
        
        showObj = sickbeard.helpers.findCertainShow(sickbeard.showList, int(show))

        if showObj == None:
            return "Show not in show list"

        if episode != None:

            epObj = showObj.getEpisode(int(season), int(episode), True)
            
            if epObj == None:
                return "Episode couldn't be retrieved"
        
            with epObj.lock:
                if epObj.status == SKIPPED:
                    epObj.status = status
                    epObj.saveToDB()

        else:
            
            myDB = db.DBConnection()
            myDB.checkDB()

            Logger().log(str(showObj.tvdbid) + ": Setting status " + str(status) + " on all episodes")
        
            sqlResults = []
    
            try:
                sql = "SELECT * FROM tv_episodes WHERE showid = " + str(showObj.tvdbid) + " AND season = " + str(season)
                Logger().log("SQL: " + sql, DEBUG)
                sqlResults = myDB.connection.execute(sql).fetchall()
            except sqlite3.DatabaseError as e:
                Logger().log("Fatal error executing query '" + sql + "': " + str(e), ERROR)
                raise

            for curEp in sqlResults:
                
                curSeason = int(curEp["season"])
                curEpisode = int(curEp["episode"])
                
                epObj = showObj.getEpisode(curSeason, curEpisode, True)
                Logger().log(str(showObj.tvdbid) + ": Setting status for " + str(curSeason) + "x" + str(curEpisode) + " to " + statusStrings[int(status)], DEBUG)
                with epObj.lock:
                    epObj.status = int(status)
                    epObj.saveToDB()
                    
        raise cherrypy.HTTPRedirect("/displayShow/?show=" + show)



    @cherrypy.expose
    def searchEpisode(self, show=None, season=None, episode=None):
        
        outStr = ""
        epObj = self._getEpisode(show, season, episode)
        
        if isinstance(epObj, str):
            return epObj
        
        tempStr = "Searching for NZB for " + epObj.prettyName()
        Logger().log(tempStr)
        outStr += tempStr + "<br />\n"
        foundNZBs = nzb.findNZB(epObj)
        
        if len(foundNZBs) == 0:
            tempStr = "No NZBs were found<br />\n"
            Logger().log(tempStr)
            outStr += tempStr + "<br />\n"
            return outStr
        
        else:

            # just use the first result for now
            Logger().log("Downloading NZB from " + foundNZBs[0].url + "<br />\n")
            result = nzb.snatchNZB(foundNZBs[0])
            
            #TODO: check if the download was successful
            
            raise cherrypy.HTTPRedirect("/displayEpisode/?show=" + str(epObj.show.tvdbid) + "&season=" + str(epObj.season) + "&episode=" + str(epObj.episode))
        
    
    @cherrypy.expose
    def processEpisode(self, dir=None, nzbName=None, jobName=None):
        
        if dir == None:
            t = Template(file="data/includes/processEpisode.html")
            return self._munge(t)
        else:
            result = processTV.doIt(dir, sickbeard.showList)
            return self._munge(result)
    
    @cherrypy.expose
    def comingEpisodes(self):
        
        epList = sickbeard.missingList + sickbeard.comingList
                
        # sort by air date
        epList.sort(lambda x, y: cmp(x.airdate.toordinal(), y.airdate.toordinal()))
        
        t = Template(file="data/includes/comingEpisodes.html")
        t.epList = epList
        t.qualityStrings = qualityStrings
        
        return self._munge(t)
        

    @cherrypy.expose
    def editConfig(self, message=None):
        
        t = Template(file="data/includes/editConfig.html")
        t.config = sickbeard.CFG
        t.message = message
        
        return self._munge(t)

    @cherrypy.expose
    def editConfigSub(self, log_dir=None, nzb_dir=None, web_username=None, web_password=None,
                   newzbin=None, newzbin_username=None, newzbin_password=None, tvbinz=None,
                   tvbinz_uid=None, tvbinz_hash=None, sab_useapi=None, sab_username=None,
                   sab_password=None, sab_apikey=None, sab_category=None, sab_host=None,
                   irc_bot=None, irc_server=None, irc_channel=None, irc_key=None, irc_nick=None,
                   xbmc_notify_onsnatch=None, xbmc_notify_ondownload=None, xbmc_update_library=None,
                   xbmc_host=None, web_port=None, web_log=None, nzb_method=None, launch_browser=None,
                   create_metadata=None):

        results = []

        if web_log == "on":
            web_log = 1
        else:
            web_log = 0
            
        if launch_browser == "on":
            launch_browser = 1
        else:
            launch_browser = 0
            
        if create_metadata == "on":
            create_metadata = 1
        else:
            create_metadata = 0
            
        if newzbin == "on":
            newzbin = 1
        else:
            newzbin = 0
            
        if tvbinz == "on":
            tvbinz = 1
        else:
            tvbinz = 0
            
        if irc_bot == "on":
            irc_bot = 1
        else:
            irc_bot = 0
            
        if xbmc_notify_onsnatch == "on":
            xbmc_notify_onsnatch = 1
        else:
            xbmc_notify_onsnatch = 0
            
        if xbmc_notify_ondownload == "on":
            xbmc_notify_ondownload = 1
        else:
            xbmc_notify_ondownload = 0
            
        if xbmc_update_library == "on":
            xbmc_update_library = 1
        else:
            xbmc_update_library = 0
            
        if not config.change_LOG_DIR(log_dir):
            results += ["Unable to create directory " + os.path.normpath(log_dir) + ", log dir not changed."]
        
        sickbeard.NZB_METHOD = nzb_method
        sickbeard.WEB_USERNAME = web_username
        sickbeard.WEB_PASSWORD = web_password
        
        sickbeard.WEB_PORT = web_port
        sickbeard.WEB_LOG = web_log

        sickbeard.LAUNCH_BROWSER = launch_browser
        sickbeard.CREATE_METADATA = create_metadata

        if not config.change_NZB_DIR(nzb_dir):
            results += ["Unable to create directory " + os.path.normpath(nzb_dir) + ", dir not changed."]

        sickbeard.NEWZBIN = newzbin
        sickbeard.NEWZBIN_USERNAME = newzbin_username
        sickbeard.NEWZBIN_PASSWORD = newzbin_password
        sickbeard.TVBINZ = tvbinz
        sickbeard.TVBINZ_UID = tvbinz_uid
        sickbeard.TVBINZ_HASH = tvbinz_hash
        sickbeard.SAB_USERNAME = sab_username
        sickbeard.SAB_PASSWORD = sab_password
        sickbeard.SAB_APIKEY = sab_apikey
        sickbeard.SAB_CATEGORY = sab_category
        sickbeard.SAB_HOST = sab_host

        config.change_IRC_BOT(irc_bot)
        config.change_IRC_SERVER(irc_server)
        config.change_IRC_CHANNEL(irc_channel, irc_key)
        config.change_IRC_NICK(irc_nick)
        
        sickbeard.XBMC_NOTIFY_ONSNATCH = xbmc_notify_onsnatch 
        sickbeard.XBMC_NOTIFY_ONDOWNLOAD = xbmc_notify_ondownload
        sickbeard.XBMC_UPDATE_LIBRARY = xbmc_update_library
        sickbeard.XBMC_HOST = xbmc_host
        
        sickbeard.save_config()
        
        if len(results) > 0:
            for x in results:
                Logger().log(x, ERROR)
            return "<br />\n".join(results)
        
        raise cherrypy.HTTPRedirect("/editConfig/?message=Config updated")



    def _getEpisode(self, show, season, episode):

        if show == None or season == None or episode == None:
            return "Invalid parameters"
        
        showObj = sickbeard.helpers.findCertainShow(sickbeard.showList, int(show))

        if showObj == None:
            return "Show not in show list"

        epObj = showObj.getEpisode(int(season), int(episode), True)
        
        if epObj == None:
            return "Episode couldn't be retrieved"

        return epObj

    def _munge(self, string):
        return unicode(string).replace("&", "&amp;").encode('ascii', 'xmlcharrefreplace')

