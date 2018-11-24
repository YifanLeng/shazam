import json
import numpy as np
import os
from scipy import spatial
import sys
import psycopg2
from psycopg2.extras import execute_batch

class Database:
    def __init__(self, host, database, user, password):
        self.host, self.database = host, database
        self.user, self.password = user, password
        try:
            # connect to postgresql
            conn = psycopg2.connect(host=host, dbname=database, \
                                    user=user, password=password)
            cur = conn.cursor()
        except:
            print("Unable to connect to database")
        
        # check if the song_info and signature table exist
        cur.execute("select to_regclass(%s)", ('public.songs_info',))
        song_info = cur.fetchone()[0]
        if song_info is None:
            cur.execute("CREATE TABLE songs_info ( \
                           song_id serial PRIMARY KEY, \
                           title text, artist text, \
                           source text);")
        cur.execute("select to_regclass(%s)", ('public.fingerprints',))
        fingerprints = cur.fetchone()[0]
        if fingerprints is None:
            # TODO: PRIMARY KEY (pair_id, song_id)
            cur.execute("CREATE TABLE fingerprints ( \
                           pair_id serial, \
                           song_id  serial REFERENCES songs_info ON DELETE CASCADE, \
                           pair_key text, \
                           pair_value integer, \
                           PRIMARY KEY (pair_id, song_id));")
        # Make the changes to the database persistent
        conn.commit()
        cur.close()
        conn.close()


    def save_to_database(self, song):
        hash_values = song.hash_values
        sql_song = "INSERT INTO songs_info(title,\
                      artist, source) VALUES \
                      (%s,%s,%s)"
        sql_fp = "INSERT INTO fingerprints(song_id, \
                    pair_key, pair_value) VALUES\
                    (%s, %s, %s)"
        
        try:
            conn = psycopg2.connect(host=self.host, dbname=self.database, \
                                    user=self.user, password=self.password)
            cur = conn.cursor()
            # insert song's info the the songs_info table
            cur.execute(sql_song, (song.title, song.artist, song.path))
            # retrieve the added song's id 
            cur.execute("SELECT LASTVAL();")
            last_id = cur.fetchone()[0]
            print(last_id)
            # insert the hash key and values of the pairs generated from the 
            # constellation map
            fingerprints = [(last_id, "({},{}):{}".format(h[0], h[1], h[2]),\
                           h[3]) for h in hash_values]
            # execute groups of statements in fewer server roundtrips.
            # for faster insertion speed
            # cur.executemany(sql_fp, fingerprints)
            execute_batch(cur, sql_fp, fingerprints)
            conn.commit()
            cur.close()
            conn.close()

        except(Exception, psycopg2.DatabaseError) as error:
            print(error)

    def remove_from_database(self, filename, logger):
        """
        remove a song object into the database
        ----------
        filename :  file, str, or pathlib.Path
            File or filename to which the data is saved. 
        Returns 
        -------
        result : int
            0 if the removal fails and 1 if it succedds
        """
        songname = filename.split(".")[0]
        filePath = os.path.join(self.path, songname + '.json')
        try:
            os.remove(filePath)
        except:
            logger.error("Failed tp remove {} from the database".format)
        

    def search(self, snippet):
        """
        search for the song that matches most closely with the snippet
        ----------
        matches :  list of tupes
            a list of (song_id, shift) tuple. shift is the difference in two 
            matching pairs' start time in snippet and song. The same shift
            means that the two pairs have the same distance in the snippet
            and the song and thus same pattern in constellation map. We look 
            for the most frequent same shift that pairs in snippet and songs 
            share. The identified song id is the one with that most frequent 
            common shift (most similar pattern).

        Returns 
        -------
        song_id : int
            the id of the song in the songs_info table
        """
        matches = self.match(snippet)
        hash_by_shift = {}
        # find the most frequent common shift
        (shift_max, max_count) = (0, 0)
        for (song_id, shift) in matches:
            if shift not in hash_by_shift:
                hash_by_shift[shift] = [song_id]
                if len(hash_by_shift[shift]) > max_count:
                    max_count = len(hash_by_shift[shift])
                    shift_max = shift
            else:
                hash_by_shift[shift].append(song_id)
                if len(hash_by_shift[shift]) > max_count:
                    max_count = len(hash_by_shift[shift])
                    shift_max = shift
        song_ids = hash_by_shift[shift_max]
        # identify the most frequent song_id
        identified_id = max(set(song_ids), key=song_ids.count)
        print(identified_id)
        return identified_id



    def match(self, snippet):
        try:
            conn = psycopg2.connect(host=self.host, dbname=self.database, \
                                    user=self.user, password=self.password)
            cur = conn.cursor()
            # create a table that stores the pairs converted from the 
            # snippet's constellation map
            cur.execute("select to_regclass(%s)", ('public.snippet_fingerprint',))
            snippet_fp = cur.fetchone()[0]
            # the last snippet info is not cleared
            if snippet_fp is not None:
                cur.execute("DROP TABLE snippet_fingerprint")
         
            cur.execute("CREATE TABLE snippet_fingerprint ( \
                            pair_id serial PRIMARY KEY, \
                            pair_key text, \
                            pair_value integer);")
            sql_fp = "INSERT INTO snippet_fingerprint( \
                        pair_key, pair_value) VALUES\
                        (%s, %s)"
            fingerprints = [("({},{}):{}".format(h[0], h[1], h[2]),\
                           h[3]) for h in snippet.hash_values]
            execute_batch(cur, sql_fp, fingerprints)
            conn.commit()
            # find entries in the fingerprints with the same pair key
            # compute the shift in time of song and snippet of the matched 
            # two pairs
            query = "SELECT f.song_id, s.pair_value-f.pair_value as shift\
                         FROM fingerprints f, snippet_fingerprint s \
                         WHERE f.pair_key = s.pair_key;"
            cur.execute(query)
            matches = cur.fetchall()
            print(len(matches))
            # TODO: drop the table
            # cur.execute("DROP TABLE snippet_fingerprint")
            #  conn.commit()
            cur.close()
            conn.close()
            return matches
        
        except(Exception, psycopg2.DatabaseError) as error:
            print(error)
        
    
 


        

   
            
                       
                





        
        

