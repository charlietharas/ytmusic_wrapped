import sqlite3
import datetime
import sys
import getopt
import json
import requests
import re
import pandas as pd
import collections
    
class Analyzer():
    
    # backbone methods
    def __init__(self, verbose, duration, more_details, use_songs, analyze_year, apikey, load, loadfp):
        self.verbose, self.duration, self.more_details, self.use_songs, self.analyze_year, self.apikey, self.load, self.loadfp = (verbose, duration, more_details, use_songs, analyze_year, apikey, load, loadfp)
        self.log = open('log.dat', 'w', encoding="utf8")
        self.main()
        
    def main(self):    
        self.file = self.open_file(sys.argv[1], ".json")
    
        print("Welcome to YouTube Music Year Wrapper v3.0")
        if self.load:
            print("Loading your preprocessed history file")
            self.songsDF = pd.read_csv(self.open_file(self.loadfp), ".csv")
        else:
            print("We are now processing your file")
            self.parse_json()
            print("Removing duplicates")
            self.delete_duplicate()
    
        if self.verbose:
            self.print_db()
        if self.duration:
            print("Getting durations. This may take a while.")
            self.get_duration()
        print("Getting top 10's")
        self.prepare_tops()
        if self.verbose:
            self.print_full_tops()
        self.log.close()
        print("Generating final report")
        self.gen_report()
        print("All done!")
        
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
                print("Could not open your history file")
                sys.exit()
        else:
            print("Your history file should be a", filetype, "file")
            sys.exit()
    
    def parse_json(self):
        self.songs = {"Title": [], "Artist": [], "Year": [], "URL": []}
        
        json_object = json.load(self.file)
        for obj in json_object:
            if (self.should_not_ignore(obj['title'], obj['time'], obj['header'])):
                if ('subtitles' in obj):
                    self.songs["Title"].append(obj['title'][8:])
                    self.songs["Artist"].append(obj['subtitles'][0]['name'].replace('- Topic ', '').replace('- Topic', ''))
                    self.songs["Year"].append(obj['time'])
                    self.songs["URL"].append(obj['titleUrl'][32:])
    
    def print_db(self):
        # VERBOSE FUNCTION TBA
        pass
    
    def prepare_tops(self):
        # Top 10 Songs
        self.songs_top = self.songsDF.nlargest(10, ['Occurrences'])
        print("--- TOP SONGS ---")
        print(self.songs_top)
        # Top 10 Artists
        occurrences = {}
        for i, v in enumerate(self.songsDF['Artist']):
            try:
                occurrences[v] += self.songsDF['Occurrences'][i]
            except:
                print(i, v)
                occurrences[v] = self.songsDF['Occurrences'][i]
        self.artists = {"Artist": occurrences.keys(), "Occurrences": occurrences.values()}
        del occurrences
        self.artistsDF = pd.DataFrame(self.artists)
        self.artistsDF.to_csv("report-artists.csv")
        self.artists_top = self.artistsDF.nlargest(10, ['Occurrences'])

        print("--- TOP ARTISTS ---")
        print(self.artists_top)
    
    def delete_duplicate(self):
        occurrences = collections.Counter(self.songs['URL'])
        self.songs['Occurrences'] = []
        for i in self.songs['URL']:
            self.songs['Occurrences'].append(occurrences[i])
        del occurrences
        
        self.historyDF = pd.DataFrame(self.songs)
        self.songsDF = pd.DataFrame(self.songs)
        self.total_songs = len(self.songsDF)
        self.songsDF.drop_duplicates(subset=['URL'], inplace=True)
        self.unique_songs = len(self.songsDF)
        self.songsDF = self.songsDF.reset_index(drop=True)
        self.songsDF.to_csv("report-songs.csv")
    
    def print_full_tops(self):
        # VERBOSE FUNCTION TBA
        pass
    
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
        print("api called", file=self.log)
        parameters = {"part": "contentDetails,snippet",
                      "id": ','.join(idlist), "key": self.apikey}
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/videos", params=parameters)
        if (response.status_code == 200):
            json_parsed = response.json()
            for item in json_parsed['items']:
                duration = self.parse_duration(item['contentDetails']['duration'])
                artist = item['snippet']['channelTitle']
                title = item['snippet']['title']
                url = item['id']
                self.cursor.execute(
                    """UPDATE report SET duration = ?, artist = ?, title = ? WHERE url = ?""", (duration, artist, title, url))
    
    def get_duration(self):
        # Count duration
        self.cursor.execute("""SELECT id, artist, title, url FROM report""")
        rows = self.cursor.fetchall()
        print("\tNumber of videos: " + str(len(rows)))
        idlist = []
        calls = 0
        for row in rows:
            idlist.append(row[3])
            if len(idlist) == 50:
                print("\tGetting info on videos " +
                      str(1+50*calls) + " - " + str(50+50*calls))
                print(','.join(idlist), file=self.log)
                self.call_api(idlist)
                calls = calls + 1
                idlist = []
        print("\tGetting info on videos " +
              str(1+50*calls) + " - " + str(len(rows)))
        print(','.join(idlist), file=self.log)
        self.call_api(idlist, self.cursor)
        self.cursor.execute("""UPDATE report SET duration = ?, artist = ?, title = ? WHERE title = ?""",
                       (0, "Unknown Artist", "Unavailable Video", "parseme"))
    
        # Calculate total duration
        if self.verbose:
            print("####################Full List WITHOUT DOUBLON AND DURATION#####################", file=self.log)
        song_count = 0
        total_duration = 0
        error_rate = 0
        self.cursor.execute(
            """SELECT id, artist, title, duration, occurence, url FROM report""")
        rows = self.cursor.fetchall()
        for row in rows:
            datetime.datetime.now()
            song_count = row[0]
            if verbose:
                print('{0} : {1} - {2}- {3} - occurence : {4} - {5}'.format(
                    row[0], row[1], row[2], row[3], row[4], row[5]), file=self.log)
            total_duration += row[3] * row[4]
            if row[3] == 0:
                error_rate = error_rate + 1
        return (total_duration, error_rate, song_count)
    
    # report generation methods
    def gen_html_report(self):
        htmlreport = open('report_{0}.html'.format(
            str(self.analyze_year)), 'w', encoding=("utf8"))
        print("""<!DOCTYPE html><html><head><title>Wrapped</title><style type="text/css">body{background-color: #000000;}.center-div{position: absolute; margin: auto; top: 0; right: 0; bottom: 0; left: 0; width: 50%; height: 90%; background-color: #000000; border-radius: 3px; padding: 10px;}.ytm_logo{width: 15%;position: relative;top: 30px;left: 40px;}.title_logo{width: 30%;position: relative;top: 30px;left: 60px;}.right_title{position: absolute;font-family: "Product Sans";top: 55px;right: 10%;font-size: 2em;color: #ffffff;}.container{position: relative;top: 13%;left: 53px;}.minutes_title{font-family: "Product Sans";font-size: 2em;color: #ffffff;}.minutes{font-family: "Product Sans";font-size: 6em;color: #ffffff;}.row{display: flex;}.column{flex: 50%;}.list{font-family: "Roboto";font-size: 1.5em;line-height: 30px;color: #ffffff;}</style></head><body><div class="center-div"><img src="ytm_logo.png" class="ytm_logo"><img src="title.png" class="title_logo"/><span class="right_title">""", file=htmlreport)
        print(str(self.analyze_year), file=htmlreport)
        print(""" Wrapped</span><div class="container"><div class="minutes_title">Minutes Listened</div><div class="minutes">""", file=htmlreport)
        if self.duration:
            print(str(self.total_minutes//60), file=htmlreport)
        else:
            print("N/A", file=htmlreport)
        print("""</div><br><br><div class="row"><div class="column"><div class="minutes_title">Top Artists</div><div class="list">""", file=htmlreport)
        if self.duration:
            #TBA LAZY
            #self.cursor.execute("""SELECT artist, occurence, duration FROM artist_count WHERE (occurence > 5) ORDER by duration DESC LIMIT 10""")
            pass
        else:
            sorted_artists = self.artists_top
            top_artists, top_occurrences = sorted_artists['Artist'], sorted_artists['Occurrences']
            durations = [0] * 10
            del sorted_artists
        for i, j, v in zip(top_artists, top_occurrences, durations):
            print("<br>", file=htmlreport)
            if self.more_details:
                if self.duration:
                    #TBA LAZY
                    #print('{0} - {1} songs ({2} mins)'.format(str(row[0]).replace(' - Topic', ''), row[1], str(row[2]//60)), file=htmlreport)
                    pass
                else:
                    print('{0} - {1} songs'.format(str(i), j), file=htmlreport)
            else:
                print('{0}'.format(i), file=htmlreport)
        print("""</div></div><div class="column"><div class="minutes_title">Top Songs</div><div class="list">""", file=htmlreport)
        sorted_songs = self.songs_top
        top_songs, top_artists, top_occurrences = sorted_songs['Title'], sorted_songs['Artist'], sorted_songs['Occurrences']
        for i, j, k in zip(top_songs, top_artists, top_occurrences):
            print("<br>", file=htmlreport)
            if self.more_details:
                print('{0} - {1} - {2} plays'.format(j, i, k), file=htmlreport)
            else:
                print('{0} - {1}'.format(j, i), file=htmlreport)
        print("""</div></div></div></div></div></body></html>""", file=htmlreport)
        htmlreport.close()
    
    def gen_report(self):
        # Top 10 Report
        report = open('report_{0}.dat'.format(
            str(self.analyze_year)), 'w', encoding=("utf8"))
        print("#################### Top Artists #####################", file=report)
        # select artist, occurrence
        sorted_artists = self.artistsDF.sort_values(by=['Occurrences'], ascending=False)
        top_artists, top_occurrences = sorted_artists['Artist'], sorted_artists['Occurrences']
        del sorted_artists
        for i, j in zip(top_artists, top_occurrences):
            print('{0} - {1}'.format(i, j), file=report)
    
        print("#################### Top Songs #####################", file=report)
        # select artist, title, occurrence
        sorted_songs = self.songsDF.sort_values(by=['Occurrences'], ascending=False)
        top_songs, top_artists, top_occurrences = sorted_songs['Title'], sorted_songs['Artist'], sorted_songs['Occurrences']
        for i, j, k in zip(top_songs, top_artists, top_occurrences):
            datetime.datetime.now()
            print('{0} - {1} - {2}'.format(j, i, k), file=report)
    
        if self.duration:
            total_duration, total_songs = 0, len(self.historyDF) # TBA
            # WILL ADD MORE STUFF AS WELL
            print("\n#################### Duration #####################", file=report)
            print('Total duration : {0}'.format(total_duration), file=report)
            print('Total song count : {0}'.format(total_songs), file=report)
        report.close()
        self.gen_html_report()
    
# flags
verbose, more_details, duration, analyze_year, use_songs, apikey, load, loadfp = (False, False, False, False, datetime.datetime.now().year, None, False, None)

opts, args = getopt.getopt(sys.argv[2:], "d:y:mv", ["duration=", "year="])
for o, token in opts:
    if o == "-v":
        verbose = True
    elif o == "-m":
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
        
analyzer = Analyzer(verbose, duration, more_details, analyze_year, use_songs, apikey, load, loadfp)