init:
	pip install ytmusicapi 
	
setup:
 	# Before calling this, find a POST request in youtubemusic dev toolsand copy the
	# request cookies to clipboard
	pbpaste | ytmusicapi browser

run:
	python3 -m src.main