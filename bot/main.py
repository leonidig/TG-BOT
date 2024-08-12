from telethon import TelegramClient, events, Button as button
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from db import Session, Main
import datetime

api_hash = "460dbd52a66709679d8d65950720fe22"
api_id = "29195129"
bot_token = "7007501488:AAHvPHGw7XxutiZUPAbO_PE2x0WEX1DzcRY"

client = TelegramClient('bot_session', api_id, api_hash).start(bot_token=bot_token)
scheduler = AsyncIOScheduler()

current_user_state = {}

character_images = {
    25: '/Users/leonidlisovskiy/Desktop/TG-BOT/bot/imgs/25.png',
    50: '/Users/leonidlisovskiy/Desktop/TG-BOT/bot/imgs/50.png',
    75: '/Users/leonidlisovskiy/Desktop/TG-BOT/bot/imgs/75.png',
    100: '/Users/leonidlisovskiy/Desktop/TG-BOT/bot/imgs/100.png',
}

def update_character_image(progress):
    return character_images.get(progress, '/Users/leonidlisovskiy/Desktop/TG-BOT/bot/imgs/25.png')

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    global sender
    sender = await event.get_sender()
    first_name = sender.first_name
    enter_tasks = [
        [button.inline("Ввести теми", b'enter_tasks')],
        [button.inline("Видалити темy", b'delete')],
        [button.inline("Відмітити як виконані", b'completed_tasks')]
    ]
    
    await event.respond(f'Привіт, {first_name}!', buttons=enter_tasks)
    
    with Session() as session:
        user = session.query(Main).filter(Main.id == sender.id).first()
        if user:
            user.owner = first_name
        else:
            user = Main(id=sender.id, owner=first_name, tasks='', due_dates='', experience=0, progress=0)
            session.add(user)
        session.commit()

@client.on(events.CallbackQuery(pattern=b'enter_tasks'))
async def enter_tasks(event):
    await event.respond("Введи свої теми і дедлайни у форматі 'тема - дедлайн', розділені ; : ")
    current_user_state[event.sender_id] = 'waiting_for_tasks'

@client.on(events.CallbackQuery(pattern=b'delete'))
async def delete_task(event):
    await event.respond("Введи назву теми для видалення: ")
    current_user_state[event.sender_id] = 'waiting_for_task_deletion'

@client.on(events.CallbackQuery(pattern=b'completed_tasks'))
async def completed_tasks(event):
    await event.respond("Введи ті теми, які ти пройшов, розділені ; : ")
    current_user_state[event.sender_id] = 'waiting_for_completed_tasks'

@client.on(events.NewMessage(pattern='/commands'))
async def send_all_commands(event):
    await event.respond('''
/set_time - зазначити час нагадувань(чч:xx)
/my_tasks - всі таски
''')

@client.on(events.NewMessage(pattern='/set_time'))
async def set_time(event):
    user_input = event.text.split()
    if len(user_input) == 2:
        time_parts = user_input[1].split(':')
        if len(time_parts) == 2 and time_parts[0].isdigit() and time_parts[1].isdigit():
            hours = int(time_parts[0])
            minutes = int(time_parts[1])

            if 0 <= hours < 24 and 0 <= minutes < 60:
                user_id = event.sender_id
                reminder_time = f'{hours:02d}:{minutes:02d}'

                with Session() as session:
                    user = session.query(Main).filter(Main.id == user_id).first()
                    if user:
                        user.reminder_time = reminder_time
                        session.commit()

                job_id = f'reminder_{user_id}'
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)

                scheduler.add_job(
                    send_user_reminder,
                    CronTrigger(hour=hours, minute=minutes),
                    args=[user_id],
                    id=job_id
                )

                await event.respond(f'Час нагадування встановлено на {reminder_time}.')
            else:
                await event.respond("Некоректний час. Переконайтеся, що години від 0 до 23, а хвилини від 0 до 59.")
        else:
            await event.respond("Введіть час у форматі ГГ:ХХ, наприклад /set_time 14:30.")
    else:
        await event.respond("Введіть команду у форматі /set_time ГГ:ХХ, наприклад /set_time 14:30.")

@client.on(events.NewMessage())
async def handle_message(event):
    user_id = event.sender_id

    if user_id in current_user_state:
        state = current_user_state[user_id]

        if state == 'waiting_for_tasks':
            tasks_input = event.text
            new_tasks = []
            new_due_dates = []

            for item in tasks_input.split(';'):
                parts = item.split('-')
                if len(parts) == 2:
                    task, due_date = parts[0].strip(), parts[1].strip()
                    new_tasks.append(task)
                    new_due_dates.append(due_date)
                else:
                    await event.respond(f"Неправильний формат: '{item}'. Будь ласка, введіть у форматі 'тема - дедлайн(рррр/мм/дд)'.")
                    return

            with Session() as session:
                user = session.query(Main).filter(Main.id == user_id).first()
                if user:
                    existing_tasks = user.tasks.split('; ') if user.tasks else []
                    existing_due_dates = user.due_dates.split('; ') if user.due_dates else []

                    all_tasks = existing_tasks + new_tasks
                    all_due_dates = existing_due_dates + new_due_dates

                    user.tasks = '; '.join(all_tasks)
                    user.due_dates = '; '.join(all_due_dates)
                    session.commit()

            del current_user_state[user_id]

            await event.respond(f'Список тем оновлено:\n' +
                                '\n'.join([f'{task} - {due_date}' for task, due_date in zip(all_tasks, all_due_dates)]))


        elif state == 'waiting_for_task_deletion':
            task_to_remove = event.text.strip().casefold()

            with Session() as session:
                user = session.query(Main).filter(Main.id == user_id).first()
                if user:
                    existing_tasks = user.tasks.split('; ') if user.tasks else []
                    existing_due_dates = user.due_dates.split('; ') if user.due_dates else []


                    normalized_tasks = [task.casefold() for task in existing_tasks]

                    if task_to_remove in normalized_tasks:
                        index = normalized_tasks.index(task_to_remove)
                        original_task = existing_tasks[index]
                        existing_tasks.pop(index)
                        existing_due_dates.pop(index)
                        user.tasks = '; '.join(existing_tasks)
                        user.due_dates = '; '.join(existing_due_dates)
                        session.commit()
                        response = f'Тема "{original_task}" видалена.'
                    else:
                        response = f'Тема "{task_to_remove}" не знайдена.'
                else:
                    response = "Користувач не знайден."

            del current_user_state[user_id]

            await event.respond(response)

        
        elif state == 'waiting_for_completed_tasks':
                completed_tasks_input = event.text.strip()
                completed_tasks = [task.strip() for task in completed_tasks_input.split(';')]
                
                with Session() as session:
                    user = session.query(Main).filter(Main.id == user_id).first()
                    if user:
                        existing_tasks = user.tasks.split('; ') if user.tasks else []
                        existing_due_dates = user.due_dates.split('; ') if user.due_dates else []
                        completed = [task for task in completed_tasks if task in existing_tasks]
                        
                        if completed:
                            total_tasks = len(existing_tasks) + len(completed_tasks)

                            for task in completed:
                                existing_tasks.remove(task)
                            user.tasks = '; '.join(existing_tasks)
                            user.due_dates = '; '.join([date for t, date in zip(existing_tasks, existing_due_dates) if t in existing_tasks])
                            user.experience += 10
                            progress = (total_tasks - len(existing_tasks)) * 100 // total_tasks
                            user.progress = progress
                            session.commit()
                            
                            character_image = update_character_image(user.progress)
                            
                            await client.send_file(event.chat_id, character_image, caption="Непогано")
                            response = f'Теми оновленно. Поточний прогрес: {user.progress}%. Зображення персонажу:'
                        else:
                            response = "Немає тем під видалення чи вони не знайдена"
                
                del current_user_state[user_id]
                
                await event.respond(response)

@client.on(events.NewMessage(pattern='/my_tasks'))
async def my_tasks(event):
    user_id = event.sender_id
    
    with Session() as session:
        user = session.query(Main).filter(Main.id == user_id).first()
        if user:
            tasks = user.tasks.split('; ') if user.tasks else []
            due_dates = user.due_dates.split('; ') if user.due_dates else []
            tasks_due_dates = [f"{task} - {date}" for task, date in zip(tasks, due_dates)]
            await event.respond(f"Твої задачі:\n" + "\n".join(tasks_due_dates))
        else:
            await event.respond("Користувач не знайден.")

async def send_user_reminder(user_id):
    with Session() as session:
        user = session.query(Main).filter(Main.id == user_id).first()
        if user:
            tasks = user.tasks.split('; ') if user.tasks else []
            due_dates = user.due_dates.split('; ') if user.due_dates else []
            if tasks:
                tasks_due_dates = [f"{task} - {date}" for task, date in zip(tasks, due_dates)]
                enter_tasks = [
                    [button.inline("Ввести теми", b'enter_tasks')],
                    [button.inline("Видалити темy", b'delete')],
                    [button.inline("Відмітити як виконані", b'completed_tasks')]
                ]
                message = f"Нагадування! Ось твої поточні задачі:\n" + "\n".join(tasks_due_dates)
                await client.send_message(user_id, message, buttons=enter_tasks)

async def main():
    scheduler.start()
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    client.loop.run_until_complete(main())
