import datetime
import sys
import getopt
import json
import requests
import re
import pandas as pd
import collections
import os
import itertools
import matplotlib.pyplot as plt

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
        
        # Top 10 Artists
        artists_top = self.artists.nlargest(10, ['Duration'])
        
        return artists_top, songs_top
    
    def meta(self):
        meta = {}
        meta["Total Minutes"] = sum(self.history["Duration"])
        meta["Total Songs"] = len(self.history["Title"])
        meta["Unique Songs"] = len(self.songs["Title"])
        meta["Unique Artists"] = len(self.artists["Artist"])
        return meta
    
    # specific optional analysis functions
    def uniques(self):
        uniques = {}
        uniques["Top 10 Unique Artists"] = collections.Counter(self.songs["Artist"]).most_common(10)
        return uniques
    
    def repeats(self):
        repeats = {}
        grouped_history = [(_, sum(1 for ii in i)) for _,i in itertools.groupby(self.history["URL"])]
        grouped_history.sort(key = lambda x : x[1])
        grouped_history.reverse()
        repeats["Most Consecutively Repeated Song"] = grouped_history[:10]
        return repeats
    
    def chronology(self):
        # this stuff will break if you are analyzing a period longer than a year
        chronology = {}
        top_songs_per_month = []
        for month in range(12):
            songs_for_month = {"Title": [], "Artist": [], "URL": [], "Duration": []}
            for j,i in enumerate(self.history["Year"]):
                if int(i[5:7]) == month+1:
                    songs_for_month["Title"].append(self.history["Title"][j])
                    songs_for_month["Artist"].append(self.history["Artist"][j])
                    songs_for_month["URL"].append(self.history["URL"][j])
                    songs_for_month["Duration"].append(self.history["Duration"][j])
        
            occurrences = collections.Counter(songs_for_month['URL'])
            songs_for_month['Occurrences'] = []
            for i in songs_for_month['URL']:
                songs_for_month['Occurrences'].append(occurrences[i])
            songs_for_month_DF = pd.DataFrame(songs_for_month)
            songs_for_month_DF.drop_duplicates(subset=['URL'], inplace=True)
            top_songs_per_month.append(songs_for_month_DF.nlargest(3, ['Occurrences']))

        chronology["Top 3 Songs Per Month"] = top_songs_per_month
        
        # TODO top dailies
        prev_day = -1
        count = 0
        days = []
        songs_for_day = {"Title": [], "Artist": [], "URL": [], "Duration": []}
        for j, i in enumerate(self.history["Year"]):
            if i[5:10] != prev_day:
                prev_day = i[5:10]
                days.append(songs_for_day)
                songs_for_day = {"Title": [], "Artist": [], "URL": [], "Duration": []}
                songs_for_day["Title"].append(self.history["Title"][j])
                songs_for_day["Artist"].append(self.history["Artist"][j])
                songs_for_day["URL"].append(self.history["URL"][j])
                songs_for_day["Duration"].append(self.history["Duration"][j])
            else:
                songs_for_day["Title"].append(self.history["Title"][j])
                songs_for_day["Artist"].append(self.history["Artist"][j])
                songs_for_day["URL"].append(self.history["URL"][j])
                songs_for_day["Duration"].append(self.history["Duration"][j])
        days.append(songs_for_day)
                
        # todo most repeated song on day
        # in the case that user doesn't really have this metric, it needs to be omitted
        # calculating whether or not they do can be done by getting most repeated song per day, getting z-score of max of this set || i'll get to it ... later
        
        del days[0]
        day_most_listened = -1 # day you listened to the most music function
        durations_per_day = [] # durations per day function
        for j, i in enumerate(days):
            urls = collections.Counter(i["URL"])
            day_most_listened = j if len(urls.values()) > day_most_listened else day_most_listened
            durations_per_day.append(sum(i["Duration"]))
            
        # since it counts from NOW to the past, this is in reverse order (this breaks of day 1 of the dataset isn't jan 1... uh oh)
        chronology["Most Diverse Day"] = [len(days) - day_most_listened , durations_per_day[day_most_listened]//60] # this is the Nth day of the year
        chronology["Durations Per Day"] = durations_per_day
        chronology["Most Musical Day"] = [len(days) - durations_per_day.index(max(durations_per_day)), max(durations_per_day)//60] # maybe several days ?? later ig
        
        # debug
        print(max(durations_per_day))
                
        return chronology
    
    def averages(self):
        averages = {}
        averages["Average Song Length"] = sum(self.history["Duration"]) / len(self.history["Duration"])
        averages["Average Song Length Unique"] = sum(self.songs["Duration"]) / len(self.songs["Duration"])
        years = []
        for i in self.history["Year"]:
            years.append(i[5:10])
        averages["Average Seconds per Day"] = sum(self.history["Duration"]) / len(collections.Counter(years))
        
        min_song_length = min(self.songs["Duration"])
        max_song_length = max(self.songs["Duration"])
        min_song_idx = list(self.songs["Duration"]).index(min_song_length)
        max_song_idx = list(self.songs["Duration"]).index(max_song_length)
        
        averages["Shortest Song"] = [min_song_length, self.songs["Title"][min_song_idx], self.songs["Artist"][min_song_idx]]
        averages["Longest Song"] = [max_song_idx, self.songs["Title"][max_song_idx], self.songs["Artist"][max_song_idx]]
        
        # 5th percentile song by duration?
        # 95th percentile song by duration?
        # median song length
        
        history_duration_sorted = self.history["Duration"].copy()
        songs_duration_sorted = self.songs["Duration"].copy()
        history_duration_sorted = list(history_duration_sorted)
        songs_duration_sorted = list(songs_duration_sorted)
        history_duration_sorted.sort()
        songs_duration_sorted.sort()
        averages["Median Song Length"] = history_duration_sorted[int(len(history_duration_sorted)/2)]
        averages["Median Song Length Unique"] = songs_duration_sorted[int(len(songs_duration_sorted)/2)]
        
        #plt.hist(list(self.songs["Duration"]), 30, (0, 600))
        #plt.show()
        
        averages["Average Replays"] = sum(self.songs["Occurrences"]) / len(self.songs["Occurrences"])
        averages["Max Replays"] = max(self.songs["Occurrences"]) # yes this statistic is already calculated somewhere else
        
        return averages
            
class Formatter():
    def gen_report(self, args, meta, artists_top, songs_top):
        
        analyze_year, duration, more_details = args
        total_minutes = meta["Total Minutes"]
        
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
more_details, duration, analyze_year, use_songs, apikey, load, loadfp = (False, False, False, datetime.datetime.now().year, None, True, os.getcwd())

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

print(" -- ANALYSIS DEBUGGING -- ")
print(" - Uniques - ")
print(analyzer.uniques())
print(" - Repeats - ")
print(analyzer.repeats())
print(" - Chronology - ")
chrono = analyzer.chronology()
for j, i in enumerate(chrono["Top 3 Songs Per Month"]):
    #print(j)
    #print(i)
    pass
print(list(chrono.items())[1])
print(list(chrono.items())[3])
print(" - Averages - ")
print(analyzer.averages())

print("All done!")