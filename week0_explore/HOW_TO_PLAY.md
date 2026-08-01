## Run the CircleMUD

We can run the CircleMUD on port `4000` with a simple docker compose up:

```sh
cd week0_explore/infrastructure
docker compose up --build
```

Some other useful Docker commands:
```sh
docker compose up --build -d # run in the background
docker compose logs -f # follow the logs
docker compose down # shut it down
```

Game data is a bind mount at `infrastructure/lib`, not a named Docker volume,
so `docker compose down -v` does not reset it. To delete all player accounts
while keeping the world data, run `./bin/reset` from the infrastructure
directory. This is destructive and cannot be undone unless the player files
were backed up.

The Docker VS Code extension provides optional click-based controls for
managing running containers.

## Connecting To CircleMUD

You can use telnet or nc to connect to the MUD:

```sh
telnet localhost 4000
nc localhost 4000
```

## Create Admin Character

On an empty player database, the first character you create becomes the
administrator. Treat it like a root account rather than a normal player.

The administrator has the following attributes:
- Level 34
- Known as the Implementor
- Top administrator role

I would recommend setting this to: `admin` / `password`

After creating your admin character:

Confirm you're admin with `score`:

```txt
> score
You are 17 years old.
  It's your birthday today.
You have 500(500) hit, 100(100) mana and 82(82) movement points.
Your armor class is 40/10, and your alignment is 0.
You have scored 7000000 exp, and have 0 gold coins.
You have been playing for 0 days and 0 hours.
This ranks you as Admin the Implementor (level 34).
You are standing.
```

Confirm you can see the Admin's commands with: `wizhelp`.

Try a couple of non-destructive admin commands: `where` and `users`:

```txt
> where
Players
-------
Admin - [1204] The Immortal Board Room
```

```txt
> users
Num Class   Name         State          Idl Login@   Site
--- ------- ------------ -------------- --- -------- ------------------------
  1 [34 Mu] Admin        Playing            16:33:48 [172.19.0.1]

1 visible sockets connected.
```

Exit out of the MUD so we can proceed to create our main character.

## Create Main Character

Create a normal test character; the examples use `dummy` and `helloworld`.
Choose any class and gender.

## Learn About Basic Commands

```sh
help time
help score
help info
help weather
help where
help who
help look
help examine
help exits
help consider
```

## Learn About Your Character

```sh
help quests
help inventory
help equipment
help experience # learn how experience works
help ac # learn about armour class
help warrior # learn about your class
help practice # learn about practicing a skill or spell
help spells # learn about spells
```

## First Steps

> I would get a pencil and paper and map out where you are.

- The Temple of Midgaard — inspect the exits and nearby rooms
- The Reading Room — leave a message on the large bulletin board
- By The Temple Altar — examine the altar
- Temple Square - drink from the temple square
- Find your guild:
  - Clerics Guild: West of Temple Square
  - Thieves Guild: South of The Dark Alley
  - Warrior Guild: East of Main Street on the south side
  - Mages Guild:  West Main Street on the south Side
- Practice at your guild, for example `practice kick`.
- Look for weak enemies and use `consider` before attacking.
  - Explore Midgaard without leaving town.
  - Loot a defeated enemy with `get all corpse`.
- Check hit points with `score`; use `rest` or `sleep` and check periodically
  until recovered.

### What if I get lost?

Disconnecting or reconnecting is not a location reset. While the server is
running, tbaMUD normally leaves the character link-dead in its current room;
logging in again reconnects to that same in-world body. A clean `quit` also
must not be treated as a guaranteed return to the Temple.

Use your map to walk back to the Temple of Midgaard. `offer` and `rent` at an
inn are equipment/rent-system commands, not a reliable navigation reset.

- [Bundled world data](infrastructure/lib/world)
