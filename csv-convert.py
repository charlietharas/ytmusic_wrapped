f = open("report-songs.dat")
x = 0

import pandas as pd

frame_dict = {"Artist": [], "Song": [], "Plays": []}
songs = pd.DataFrame(frame_dict)

for i in f:
    try:
        y = i.split(' - ')
        if y[1] == 'Topic':
            songs = songs.append({"Artist": y[0], "Song": y[2], "Plays": int(y[-1])}, ignore_index=True)
        else:
            songs = songs.append({"Artist": y[1], "Song": y[2], "Plays": int(y[-1])}, ignore_index=True)

    except:
        continue
    
songs.to_csv("report-songs.csv")

print(len(songs))

f = open("report-artists.dat")

frame_dict = {"Artist": [], "Plays": []}
artists = pd.DataFrame(frame_dict)

for i in f:
    try:
        y = i.split(' - ')
        artists = artists.append({"Artist": y[0], "Plays": int(y[-1])}, ignore_index=True)

    except:
        continue
    
artists.to_csv("report-artists.csv")
print(len(artists))