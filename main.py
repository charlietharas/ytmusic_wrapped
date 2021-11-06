﻿import sqlite3
import datetime
import sys
import getopt
import json
import requests
import re
import pandas as pd
import collections
import os

class Loader():
    # backbone methods
    def __init__(self, duration, more_details, use_songs, analyze_year, apikey):
        self.duration, self.more_details, self.use_songs, self.analyze_year, self.apikey = (duration, more_details, use_songs, analyze_year, apikey)
        self.file = self.open_file(sys.argv[1], ".json")
        
    # utility methods
    def should_not_ignore(self, title, year, header):
        if (header == "YouTube Music" and title[:7] == "Watched" and year[:4] == str(self.analyze_year)):
            return True
        return False
    
    def open_file(self, filepath, filetype):
        if (filepath.endswith(filetype)):
            try:
                file = open(filepath, "r", encoding="utf8")
                return file
            except:
                print("Could not open your report file")
                sys.exit()
        else:
            print("There was an error opening your report files.")
            sys.exit()
            
    
    # processes bulk lists
    def parse_json(self):
        self.history = {"Title": [], "Artist": [], "Year": [], "URL": [], "Duration": []}
        json_object = json.load(self.file)
        for obj in json_object:
            if (self.should_not_ignore(obj['title'], obj['time'], obj['header'])):
                if ('subtitles' in obj):
                    self.history["Title"].append(obj['title'][8:])
                    self.history["Artist"].append(obj['subtitles'][0]['name'].replace('- Topic ', '').replace('- Topic', ''))
                    self.history["Year"].append(obj['time'])
                    self.history["URL"].append(obj['titleUrl'][32:])
                    self.history["Duration"].append(0)
                    
        occurrences = collections.Counter(self.history['URL'])
        self.history['Occurrences'] = []
        for i in self.history['URL']:
            self.history['Occurrences'].append(occurrences[i])
                    
        occurrences = collections.Counter(self.history['Artist'])
        duration = [0]*len(occurrences.keys())
        self.artists = {"Artist": occurrences.keys(), "Occurrences": occurrences.values(), "Duration": duration}
    
    # generates dataframes and csv files
    def gen_csvs(self):
        self.historyDF = pd.DataFrame(self.history)
        self.historyDF.to_csv("report-history.csv")
        
        self.artistsDF = pd.DataFrame(self.artists)
        self.artistsDF.to_csv("report-artists.csv")
        
        self.songsDF = pd.DataFrame(self.history)
        self.total_songs = len(self.songsDF)
        # TODO more comprehensive duplicate dropping function (much further down the line)
        self.songsDF.drop_duplicates(subset=['URL'], inplace=True)
        self.unique_songs = len(self.songsDF)
        self.songsDF = self.songsDF.reset_index(drop=True)
        self.songsDF.to_csv("report-songs.csv")
    
    # API management functions
    def parse_duration(self, duration):
        timestr = duration
        time = re.findall(r'\d+', timestr)
        length = len(time)
        if length > 4:
            return 0
        if length == 4:
            return ((int(time[0])*24*60*60)+(int(time[1])*60*60)+int(time[2]*60)+(int(time[3])))
        elif length == 3:
            return ((int(time[0])*60*60)+(int(time[1])*60)+(int(time[2])))
        elif length == 2:
            return ((int(time[0])*60)+(int(time[1])))
        elif length == 1:
            return (int(time[0]))
        else:
            return 0
    
    def call_api(self, idlist):
        parameters = {"part": "contentDetails,snippet",
                      "id": ','.join(idlist), "key": self.apikey}
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/videos", params=parameters)
        
        if (response.status_code == 200):
            json_parsed = response.json()
            for item in json_parsed['items']:
                duration = self.parse_duration(item['contentDetails']['duration'])
                url = item['id']
                if duration < 10:
                    duration = duration * 60
                
                # update by url
                for (j, i) in enumerate(self.history["URL"]):
                    if i == url:
                        if duration >= 10:
                            self.history["Duration"][j] = duration
    
    def get_duration(self):
        # Count duration
        idlist = []
        calls = 0
        unique_song_urls = set(self.history['URL'])
        print("Getting durations. This may take a while. Awaiting", len(unique_song_urls), "requests.")
        for url in unique_song_urls:
            idlist.append(url)
            if len(idlist) == 50:
                print("\tGetting info on videos " +
                      str(1+50*calls) + " - " + str(50+50*calls))
                self.call_api(idlist)
                calls += 1
                idlist = []
        print("\tGetting info on videos " +
              str(1+50*calls) + " - " + str(len(unique_song_urls)))
        self.call_api(idlist)
        
        # update artist durations
        # i know this section is garbage i'll make it nicer later
        artist_durations = {}
        for i in range(len(self.history["Artist"])):
            duration = self.history["Duration"][i]
            artist = self.history["Artist"][i]
            try:
                artist_durations[artist] += duration
            except:
                artist_durations[artist] = duration
                
        occurrences = collections.Counter(self.history["Artist"])
        artists_dict = collections.defaultdict(list)
        for i in (artist_durations, occurrences):
            for key, val in i.items():
                artists_dict[key].append(val)
                
        durations = []
        occurrences = []
        for i, j in artists_dict.values():
            durations.append(i)
            occurrences.append(j)
            
        self.artists = {"Artist": artists_dict.keys(), "Occurrences": occurrences, "Duration": durations}
        
        self.gen_csvs()
        
    def outs(self):
        print("We are now processing your file")
        self.parse_json()            

        if self.duration:
            self.get_duration()
        else:
            self.gen_csvs() # generates dataframes and CSVs
        
        return self.historyDF, self.artistsDF, self.songsDF
    
    def load(self, loadfp):
        print("Loading your preprocessed history files")
        historyDF = pd.read_csv(self.open_file(os.path.join(loadfp, "report-history.csv"), ".csv"))
        artistsDF = pd.read_csv(self.open_file(os.path.join(loadfp, "report-artists.csv"), ".csv"))
        songsDF = pd.read_csv(self.open_file(os.path.join(loadfp, "report-songs.csv"), ".csv"))
        return historyDF, artistsDF, songsDF


class Analyzer():
    def __init__(self, historyDF, artistsDF, songsDF):
        self.history = historyDF
        self.artists = artistsDF
        self.songs = songsDF

    def tops(self):
        # Top 10 Songs
        songs_top = self.songs.nlargest(10, ['Occurrences'])
        print("--- TOP SONGS ---")
        print(songs_top)
        
        # Top 10 Artists
        print(self.artists.head())
        artists_top = self.artists.nlargest(10, ['Duration'])
        print("--- TOP ARTISTS ---")
        print(artists_top)
        
        return artists_top, songs_top
    
    def meta(self):
        total_minutes = sum(self.history["Duration"])
        return (total_minutes)
    
class Formatter():
    def gen_report(self, args, meta, artists_top, songs_top):
        
        analyze_year, duration, more_details = args
        total_minutes = meta
        
        # TODO rewrite HTML report generation        
        # TODO Calculate total duration
        htmlreport = open('report_{0}.html'.format(
            str(analyze_year)), 'w', encoding=("utf8"))
        print("""<!DOCTYPE html><html><head><title>Wrapped</title><style type="text/css">body{background-color: #000000;}.center-div{position: absolute; margin: auto; top: 0; right: 0; bottom: 0; left: 0; width: 50%; height: 90%; background-color: #000000; border-radius: 3px; padding: 10px;}.ytm_logo{width: 15%;position: relative;top: 30px;left: 40px;}.title_logo{width: 30%;position: relative;top: 30px;left: 60px;}.right_title{position: absolute;font-family: "Product Sans";top: 55px;right: 10%;font-size: 2em;color: #ffffff;}.container{position: relative;top: 13%;left: 53px;}.minutes_title{font-family: "Product Sans";font-size: 2em;color: #ffffff;}.minutes{font-family: "Product Sans";font-size: 6em;color: #ffffff;}.row{display: flex;}.column{flex: 50%;}.list{font-family: "Roboto";font-size: 1.5em;line-height: 30px;color: #ffffff;}</style></head><body><div class="center-div"><img src="ytm_logo.png" class="ytm_logo"><img src="title.png" class="title_logo"/><span class="right_title">""", file=htmlreport)
        print(str(analyze_year), file=htmlreport)
        print(""" Wrapped</span><div class="container"><div class="minutes_title">Minutes Listened</div><div class="minutes">""", file=htmlreport)
        if duration:
            print(str(total_minutes//60), file=htmlreport)
        else:
            print("N/A", file=htmlreport)
        print("""</div><br><br><div class="row"><div class="column"><div class="minutes_title">Top Artists</div><div class="list">""", file=htmlreport)

        print(artists_top.columns)
        for i, j, v in zip(artists_top["Artist"], artists_top["Occurrences"], artists_top["Duration"]): # TODO add durations to artist stuff
            print("<br>", file=htmlreport)
            if more_details:
                if duration:
                    print('{0} - {1} songs ({2} mins)'.format(str(i), j, str(v//60)), file=htmlreport) # TODO v should be artist duration (?)
                    pass
                else:
                    print('{0} - {1} songs'.format(str(i), j), file=htmlreport)
            else:
                print('{0}'.format(i), file=htmlreport)
        print("""</div></div><div class="column"><div class="minutes_title">Top Songs</div><div class="list">""", file=htmlreport)
        top_songs, top_artists, top_occurrences = songs_top['Title'], songs_top['Artist'], songs_top['Occurrences']
        for i, j, k in zip(top_songs, top_artists, top_occurrences):
            print("<br>", file=htmlreport)
            if more_details:
                print('{0} - {1} - {2} plays'.format(j, i, k), file=htmlreport)
            else:
                print('{0} - {1}'.format(j, i), file=htmlreport)
        print("""</div></div></div></div></div></body></html>""", file=htmlreport)
        htmlreport.close()
    
# flags
# TODO fix parameter/flags system
more_details, duration, analyze_year, use_songs, apikey, load, loadfp = (False, False, False, datetime.datetime.now().year, None, False, os.getcwd())

opts, args = getopt.getopt(sys.argv[2:], "d:y:mv", ["duration=", "year="])
for o, token in opts:
    if o == "-m":
        more_details = True
    elif o in ("-d", "--duration"):
        duration = True
        apikey = token
    elif o in ("-y", "--year"):
        analyze_year = token
    elif o in ("-s", "--songs"):
        use_songs = True
    elif o in ("-l", "--load"):
        load = True
        loadfp = token
                
loader = Loader(duration, more_details, analyze_year, use_songs, apikey)
if load:
    history, artists, songs = loader.load(loadfp)
else:
    history, artists, songs = loader.outs()

analyzer = Analyzer(history, artists, songs)
artists_top, songs_top = analyzer.tops()
meta = analyzer.meta()

formatter = Formatter() 
formatter.gen_report((analyze_year, duration, more_details), meta, artists_top, songs_top)

print("All done!")