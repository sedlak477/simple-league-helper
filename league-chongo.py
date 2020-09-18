import requests as r
import bs4 as bs
import socket
import time
import threading
import curses, curses.panel


SSL_CERT = "./riotgames.pem"
GAME_START_POLL_INTERVAL = 10  # In seconds

SKILL_OFFSET_LEFT = 5
SKILL_OFFSET_BOTTOM = 9
ITEM_OFFSET_MID = -6
ITEM_OFFSET_TOP = 5
NAME_OFFSET_TOP = 2
NAME_OFFSET_LEFT = 5
STATS_OFFSET_LEFT = 1
STATS_OFFSET_TOP = 2

CLIENT_ADDRESS = ("localhost", 2999)


def isGameRunning():
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.settimeout(GAME_START_POLL_INTERVAL)
    try:
        test_socket.connect(CLIENT_ADDRESS)
        test_socket.close()
        return True
    except:
        return False

def waitForGame():
    while not isGameRunning():
        time.sleep(GAME_START_POLL_INTERVAL)


def parseItemsTable(table):
    item_sets = []
    rows = table.find_all("ul", class_="champion-stats__list")

    for row in rows:
        items = row.find_all("li", class_="champion-stats__list__item")
        item_set = []
        for item in items:
            text = item["title"]
            mini_soup = bs.BeautifulSoup(text, "lxml")
            item_set.append(mini_soup.b.string)
        item_sets.append(item_set)

    categories = {
        "starters": item_sets[:2],
        "boots": item_sets[-3:],
        "builds": item_sets[2:-3]
    }

    return categories


def parseAbilitiesTable(table):
    abilities = []
    abilities_raw = table.find_all("tbody")[1].ul.find_all("li", class_="champion-stats__list__item")

    for ability in abilities_raw:
        text = ability["title"]
        key = ability.span.string
        mini_soup = bs.BeautifulSoup(text, "lxml")
        abilities.append(key + ": " + mini_soup.b.string)

    return abilities


def getOPGGChampionData(champion):
    champion = "".join(filter(lambda char: char.isalnum(), champion.lower()))
    req = r.get(f"https://euw.op.gg/champion/{champion.lower()}")
    soup = bs.BeautifulSoup(req.text, "lxml")
    (raw_abilities_table, raw_items_table, _) = soup.find_all("table", class_="champion-overview__table")
    
    abilities_table = parseAbilitiesTable(raw_abilities_table)
    items_table = parseItemsTable(raw_items_table)

    return {
        "items": items_table,
        "abilities": abilities_table
    }


def getPlayerlist():
    req = r.get(f"https://{CLIENT_ADDRESS[0]}:{CLIENT_ADDRESS[1]}/liveclientdata/playerlist", verify=SSL_CERT)
    return req.json()


def getSummonerName():
    req = r.get(f"https://{CLIENT_ADDRESS[0]}:{CLIENT_ADDRESS[1]}/liveclientdata/activeplayername", verify=SSL_CERT)
    return req.json()


def getSummonerData():
    activeSummoner = getSummonerName()
    playerlist = getPlayerlist()
    summoner_data = filter(lambda data: data["summonerName"] == activeSummoner, playerlist)
    return next(summoner_data)


def getCurrentStats():
    req = r.get(f"https://{CLIENT_ADDRESS[0]}:{CLIENT_ADDRESS[1]}/liveclientdata/activeplayer", verify=SSL_CERT)
    return req.json()["championStats"]

def displayStats(win):
    data = getCurrentStats() if isGameRunning() else {}
    win.clear()
    win.addstr(0, 0, f"AD:  {data.get('attackDamage', 0):.0f}");       win.addstr(0, 12, f"AP: {data.get('abilityPower', 0):.0f}")
    win.addstr(1, 0, f"Res: {data.get('armor', 0):.0f}");              win.addstr(1, 12, f"MR: {data.get('magicResist', 0):.0f}")
    win.addstr(2, 0, f"AS:  {data.get('attackSpeed', 0):.2f}");        win.addstr(2, 12, f"CD: {data.get('cooldownReduction', 0) * -100:.0f}%")
    win.addstr(3, 0, f"Crt: {data.get('critChance', 0) * 100:.0f}%");  win.addstr(3, 12, f"MV: {data.get('moveSpeed', 0):.0f}")
    win.refresh()


def run_app(stdscr, championName=None, summonerName=None):
    curses.curs_set(0)  # Set cursor invisible

    height, width = stdscr.getmaxyx()
    mid = width // 2
    v_mid = height // 2

    if championName is None:
        stdscr.clear()
        WAIT_MSG = "Waiting for game to start..."
        stdscr.addstr(v_mid, mid - len(WAIT_MSG) // 2 - 1, WAIT_MSG)
        stdscr.refresh()

        waitForGame()

    stdscr.clear()
    LOADING_MSG = "Loading champion information..."
    stdscr.addstr(v_mid, mid - len(LOADING_MSG) // 2 - 1, LOADING_MSG)
    stdscr.refresh()

    if championName is None:
        data = getSummonerData()
        summonerName = data["summonerName"]
        championName = data["championName"]

    champion_data = getOPGGChampionData(championName)

    stdscr.clear()

    # Print champion name
    stdscr.addstr(NAME_OFFSET_TOP, NAME_OFFSET_LEFT, f"{summonerName} playing {championName}" if summonerName is not None else championName)

    # Print skill order
    stdscr.addstr(height - SKILL_OFFSET_BOTTOM, SKILL_OFFSET_LEFT, "Skill order:")
    for i, skill in enumerate(champion_data["abilities"]):
        stdscr.addstr(height - SKILL_OFFSET_BOTTOM + 2 + i, SKILL_OFFSET_LEFT + 2, f"{i + 1}. {skill}")

    # Print starting items
    stdscr.addstr(ITEM_OFFSET_TOP, mid + ITEM_OFFSET_MID, "Starting items:")
    for i, items in enumerate(champion_data["items"]["starters"]):
        stdscr.addstr(ITEM_OFFSET_TOP + 2 + i, mid + ITEM_OFFSET_MID + 2, f"{i + 1}. {', '.join(items)}")

    # Print common builds
    stdscr.addstr(ITEM_OFFSET_TOP + len(champion_data["items"]["starters"]) + 4, mid + ITEM_OFFSET_MID, "Core items:")
    for i, items in enumerate(champion_data["items"]["builds"]):
        stdscr.addstr(ITEM_OFFSET_TOP + len(champion_data["items"]["starters"]) + 6 + i, mid + ITEM_OFFSET_MID + 2, f"{i + 1}. {', '.join(items)}")

    # Print boots
    stdscr.addstr(ITEM_OFFSET_TOP + len(champion_data["items"]["starters"]) + len(champion_data["items"]["builds"]) + 8, mid + ITEM_OFFSET_MID, "Boots:")
    for i, items in enumerate(champion_data["items"]["boots"]):
        stdscr.addstr(ITEM_OFFSET_TOP + len(champion_data["items"]["starters"]) + len(champion_data["items"]["builds"]) + 10 + i, mid + ITEM_OFFSET_MID + 2, f"{i + 1}. {', '.join(items)}") 

    stdscr.addstr(height - 1, 0, "| q = Quit | r = Refresh |")
    stdscr.refresh()

    panel_height = height - (SKILL_OFFSET_BOTTOM + NAME_OFFSET_TOP + 1 + STATS_OFFSET_TOP)
    panel_width = mid - (NAME_OFFSET_LEFT - ITEM_OFFSET_MID + STATS_OFFSET_LEFT)

    win = curses.newwin(panel_height, panel_width, NAME_OFFSET_TOP + 1 + STATS_OFFSET_TOP, NAME_OFFSET_LEFT + STATS_OFFSET_LEFT)
    panel = curses.panel.new_panel(win)

    def statsUpdateLoop():
        while True:
            displayStats(win)
            time.sleep(5)
            stdscr.refresh()

    statsUpdateThread = threading.Thread(target=statsUpdateLoop)
    statsUpdateThread.setDaemon(True)
    statsUpdateThread.start()

    # Wait for command
    quit = False
    while not quit:
        key = stdscr.getkey()
        if key == "q":
            quit = True


if __name__ == "__main__":
    try:
        curses.wrapper(run_app)
    except KeyboardInterrupt:
        pass
