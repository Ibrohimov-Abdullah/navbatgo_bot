# main.py
from threading import Thread
from admin_bot import startadmin
from barber_bot import startbarber
from user_bot import startuser

Thread(target=startadmin).start()
Thread(target=startbarber).start()
Thread(target=startuser).start()

print("All bots are running...")
