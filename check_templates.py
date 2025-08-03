import os

print("Current folder:", os.getcwd())
print("Templates folder exists:", os.path.isdir("templates"))
print("presence.html exists:", os.path.isfile("templates/presence.html"))
