from stem import Signal
from stem.control import Controller
import requests

# Function to change the Tor IP address
def change_tor_identity():
    with Controller.from_port(port = 9051) as controller:
        controller.authenticate(password='kiwi') #password='your_password'
        controller.signal(Signal.NEWNYM)

# Configure a session to use Tor as a proxy
def get_tor_session():
    session = requests.session()
    session.proxies = {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050'
    }
    return session

# Example usage
if __name__ == "__main__":
    # Change Tor identity
    change_tor_identity()

    # Use the Tor session to make a request
    session = get_tor_session()
    print("One:\n")
    response = session.get('http://httpbin.org/ip')  # A service that returns your IP address
    print(response.text)
    print("Two:\n")
    response = session.get('http://google.com')  # A service that returns your IP address
    print(response.text)