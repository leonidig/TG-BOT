from telethon import TelegramClient, events, Button as button
from db import Session, Main
from sqlalchemy import select

api_hash = "460dbd52a66709679d8d65950720fe22"
api_id = "29195129"
bot_token = "7007501488:AAHvPHGw7XxutiZUPAbO_PE2x0WEX1DzcRY"

client = TelegramClient('bot_session', api_id, api_hash).start(bot_token=bot_token)

current_user_state = {}

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    global sender
    sender = await event.get_sender()
    first_name = sender.first_name
    enter_tasks = [
        [button.inline("Ввести задания", b'enter_tasks')],
        [button.inline("Відмітити як виконане", b'delete')]
    ]
    
    await event.respond(f'Hello, {first_name}!', buttons=enter_tasks)
    
    with Session() as session:
        user = session.query(Main).filter(Main.id == sender.id).first()
        if user:
            user.owner = first_name
        else:
            user = Main(id=sender.id, owner=first_name, tasks='')
            session.add(user)
        session.commit()

@client.on(events.CallbackQuery(pattern=b'enter_tasks'))
async def enter_tasks(event):
    await event.respond("Введи свої завдання (обовʼязково розділи комами): ")
    current_user_state[event.sender_id] = 'waiting_for_tasks'

@client.on(events.CallbackQuery(pattern=b'delete'))
async def delete_task(event):
    await event.respond("Введи назву таску який хочеш відмітити як виконаний: ")
    current_user_state[event.sender_id] = 'waiting_for_task_deletion'

@client.on(events.NewMessage())
async def handle_message(event):
    user_id = event.sender_id
    
    if user_id in current_user_state:
        state = current_user_state[user_id]
        
        if state == 'waiting_for_tasks':
            tasks_input = event.text
            
            new_tasks = [task.strip() for task in tasks_input.split(',')]
            
            with Session() as session:
                user = session.query(Main).filter(Main.id == user_id).first()
                if user:
                    existing_tasks = user.tasks.split(', ') if user.tasks else []
                    all_tasks = list(set(existing_tasks + new_tasks))
                    user.tasks = ', '.join(all_tasks)
                    session.commit()
            
            del current_user_state[user_id]
            
            await event.respond(f'Список завдань оновлено: {", ".join(all_tasks)}')
        
        elif state == 'waiting_for_task_deletion':
            task_to_remove = event.text.strip()
            
            with Session() as session:
                user = session.query(Main).filter(Main.id == user_id).first()
                if user:
                    existing_tasks = user.tasks.split(', ') if user.tasks else []
                    if task_to_remove in existing_tasks:
                        existing_tasks.remove(task_to_remove)
                        user.tasks = ', '.join(existing_tasks)
                        session.commit()
                        response = f'Задача "{task_to_remove}" видалена.'
                    else:
                        response = f'Задача "{task_to_remove}" не знайдена.'
                else:
                    response = "Юзер не знайден."
            
            del current_user_state[user_id]
            
            await event.respond(response)

@client.on(events.NewMessage(pattern='/my_tasks'))
async def send_user_tasks(event):
    sender = await event.get_sender()
    with Session() as session:
        user = session.query(Main).filter(Main.id == sender.id).first()
        if user:
            tasks = user.tasks if user.tasks else "Нет задач."
            await event.respond(f"Твої завдання: {tasks}")
        else:
            await event.respond("Юзер не знайден")

async def main():
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    client.loop.run_until_complete(main())
