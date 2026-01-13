# main.py
from threading import Thread
from admin_bot import start_bot1
from barber_bot import start_bot2
from user_bot import start_bot3

Thread(target=start_bot1).start()
Thread(target=start_bot2).start()
Thread(target=start_bot3).start()

print("All bots are running...")
