# Copyright 2015 Adafruit Industries.
# Author: Tony DiCola
# License: GNU GPLv2, see LICENSE.txt
import random
from os.path import basename, splitext
from typing import Optional, Union
from collections import deque

random.seed()

class Movie:
    """Representation of a movie"""

    def __init__(self, target:str , title: Optional[str] = None, repeats: int = 1):
        """Create a playlist from the provided list of movies."""
        self.target = target
        self.filename = basename(target)
        self.title = title
        self.repeats = int(repeats)
        self.playcount = 0

    def was_played(self):
        if self.repeats > 1:
            # only count up if its necessary, to prevent memory exhaustion if player runs a long time
            self.playcount += 1
        else:
            self.playcount = 1

    def clear_playcount(self):
        self.playcount = 0
        
    def finish_playing(self):
        self.playcount = self.repeats
    
    def __lt__(self, other):
        return self.target < other.target

    def __eq__(self, other):
        if isinstance(other, str):
            return self.filename == other or self.title == other or self.title == splitext(other)[0]
        if isinstance(other, Movie):
            return self.target == other.target
        return False

    def __str__(self):
        return f"{self.filename} ({self.title})" if self.title else self.filename

    def __repr__(self):
        return repr((self.target, self.filename, self.title, self.repeats, self.playcount))

class Playlist:
    """Representation of a playlist of movies."""

    def __init__(self, movies, is_random, is_random_unique, resume_playlist):
        """Create a playlist from the provided list of movies."""
        self._movies = movies
        self._index = None
        self._next = None
        # history stack of played movies to support 'back' in random mode
        # bounded to avoid unbounded memory growth
        self._history = deque(maxlen=100)
        self._is_random = is_random
        self._is_random_unique = is_random_unique
        self._resume = resume_playlist

    def get_next(self) -> Movie:
        """Get the next movie in the playlist. Will loop to start of playlist
        after reaching end.
        """
        # Check if no movies are in the playlist and return nothing.
        if len(self._movies) == 0:
            return None
        
        # Check if next movie is set and jump directly there:
        if self._next is not None:
            next = self._next
            self._next = None # reset next
            # push previous to history if exists
            if self._index is not None:
                try:
                    self._history.append(self._movies[self._index])
                except Exception:
                    pass
            self._index = self._movies.index(next)
            return next

        # check if any movie is set to infinite repeats and return it
        # this must be after the _next check so jumping to a specific movie still works
        for m in self._movies:
            if getattr(m, "repeats", None) == -1:
                self._next = None
                self._index = self._movies.index(m)
                return m

        # Start Random movie
        if self._is_random:
            # push previous to history if exists
            if self._index is not None:
                try:
                    self._history.append(self._movies[self._index])
                except Exception:
                    pass
            self._index = self._movies.index(self._select_random_movie())
        else:
            # Start at the first movie or resume and increment through them in order.
            if self._index is None:
                if self._resume:
                    try:
                        with open("playlist_index.txt", "r") as f:
                            self._index = int(f.read())
                    except FileNotFoundError:
                        self._index = 0
                else:
                    self._index = 0
            else:
                self._index += 1
                
            # Wrap around to the start after finishing.
            if self._index >= self.length():
                self._index = 0

            # push previous to history if exists (sequential case)
            # Note: when starting from None there is no previous
            # so only push when _index was previously set (handled above for random)
            # For sequential we pushed before incrementing index, so no extra action here.

        if self._resume:
            with open("playlist_index.txt","w") as f:
                f.write(str(self._index))

        return self._movies[self._index]
    
    # sets next by filename or Movie object or index
    def set_next(self, thing: Union[Movie, str, int]):
        if isinstance(thing, Movie):
            if (thing in self._movies):
                self._next = thing
        elif isinstance(thing, str):
            if thing in self._movies:
                self._next = self._movies[self._movies.index(thing)]
            elif thing[0:1] in ("+","-"):
                self._next = self._movies[(self._index+int(thing))%self.length()]
        elif isinstance(thing, int):
            if thing >= 0 and thing <= self.length():
                self._next = self._movies[thing]
        else:
            self._next = None
        if not (self._is_random and self._is_random_unique):
            self.clear_all_playcounts()
        self._movies[self._index].finish_playing() #set the current to max playcount so it will not get played again
       
    # sets next relative to current index
    def seek(self, amount:int):
        self.set_next((self._index+amount)%self.length())
        if self._is_random:
            self.set_next(self._select_random_movie())
            
    def _select_random_movie(self) -> Movie:
        """Select a random movie from the playlist."""
        
        if self._is_random_unique:
            # select randomly from unplayed movies
            unplayed_movies = [m for m in self._movies if m.playcount < m.repeats]
            if len(unplayed_movies) == 0:
                # all movies played, reset playcounts
                self.clear_all_playcounts()
                unplayed_movies = self._movies
            return random.choice(unplayed_movies)
        else:
            # select randomly from all movies
            return random.choice(self._movies)

    def length(self):
        """Return the number of movies in the playlist."""
        return len(self._movies)

    def clear_all_playcounts(self):
        for movie in self._movies:
            movie.clear_playcount()

    def go_back(self) -> bool:
        """Set the next movie to the last played movie from history.

        Returns True if history had an entry and next was set, False otherwise.
        """
        if not hasattr(self, '_history') or len(self._history) == 0:
            return False
        prev = self._history.pop()
        if prev in self._movies:
            self._next = prev
            return True
        return False
    
    def __str__(self):
        if self._is_random:
            playbackmode = f'Random ({"unique" if self._is_random_unique else "all"})'
        else:  
            playbackmode = 'Sequential'
        info = f"Mode: {playbackmode}, Resume: {self._resume}\n"
        for m in self._movies:
            info += f"Movie: {str(m)}, Repeats: {m.repeats}, Played: {m.playcount}\n"
        return info