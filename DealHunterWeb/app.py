from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("flask_hidden_key", "DH_hidden_key")

print("Starting Deal Hunter...")

API_KEY = os.getenv("SCRAPER_API_KEY")
sender_email = os.getenv("EMAIL_SENDER")
app_password = os.getenv("EMAIL_PASSWORD")

active_trackers = []


def check():
    if len(active_trackers) == 0:
        return

    print("Checking", len(active_trackers), "links right now...")
    
    for product in active_trackers:
        target_url = product['url']
        scraper = f"http://api.scraperapi.com?api_key={API_KEY}&url={target_url}&render=true"
        
        try:
            response = requests.get(scraper)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                clean_price = None
                
                
                if "skroutz.gr" in target_url:
                    price_box = soup.find("div", class_="final-price")
                    if price_box:
                        integer = price_box.find("span", class_="integer-part").text.strip()
                        decimal = price_box.find("span", class_="decimal-part").text.strip().replace(",", "")
                        clean_price = float(f"{integer}.{decimal}")
                        print("Found skroutz price:", clean_price)

                
                elif "bestprice.gr" in target_url or "shopflix.gr" in target_url:
                    all_strings = soup.stripped_strings
                    euro = []
                    for text in all_strings:
                        if '€' in text:
                            euro.append(text)
                            
                    for text in euro:
                        raw_price = text.replace("Από", "").replace("από", "").replace("€", "").strip()
                        
                        number_str = ""
                        for char in raw_price:
                            if char.isdigit() or char in ".,":
                                number_str += char
                                
                        if number_str != "":
                            number_str = number_str.replace(".", "").replace(",", ".")
                            try:
                                clean_price = float(number_str)
                                print("Found alternate price:", clean_price)
                                break 
                            except Exception:
                                pass
                                
                
                else:
                    all_strings = soup.stripped_strings
                    euro = []
                    for text in all_strings:
                        if '€' in text:
                            euro.append(text)
                            
                    for text in euro:
                        raw_price = text.replace("Από", "").replace("από", "").replace("€", "").strip()
                        
                        number_str = ""
                        for char in raw_price:
                            if char.isdigit() or char in ".,":
                                number_str += char
                                
                        if number_str != "":
                            number_str = number_str.replace(".", "").replace(",", ".")
                            try:
                                clean_price = float(number_str)
                                print("Found price:", clean_price)
                                break 
                            except Exception:
                                pass

               
                if clean_price != None:
                    if clean_price <= product['budget']:
                        print("Price dropped. Sending email.")
                        
                        subject = "Deal Hunter: Price Drop"
                        body = f"The product dropped to {clean_price} EUR.\nBuy it here: {target_url}"
                        
                        msg = MIMEText(body)
                        msg['Subject'] = subject
                        msg['From'] = sender_email
                        msg['To'] = product['email']
                        
                        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                            server.login(sender_email, app_password)
                            server.sendmail(sender_email, product['email'], msg.as_string())
                            
                        
                        active_trackers.remove(product)
                        
        except Exception as e:
            print("Error checking background task:", e)


scheduler = BackgroundScheduler()
scheduler.add_job(func=check, trigger="interval", minutes=1) #0.3 only for testing!!!!!!
scheduler.start()




@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_email = request.form.get("login_email")
        
        if login_email != "" and login_email != None:
            session['user_email'] = login_email
            flash(f"Logged in as {login_email}.", "success")
        else:
            session['user_email'] = "Guest"
            flash("Continuing as Guest. Enter your email when adding a tracker.", "info")
            
        return redirect(url_for('tracker'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear() 
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

@app.route('/app', methods=['GET', 'POST'])
def tracker():
    
    if 'user_email' not in session:
        return redirect(url_for('login'))
        
    current_user = session['user_email']

    if request.method == 'POST':
        if current_user == "Guest":
            receiver_email = request.form.get("user_email")
        else:
            receiver_email = current_user
            
        item_url = request.form.get("item_link")
        user_budget = float(request.form.get("target_price"))
        
        label_input = request.form.get("label", "")
        if label_input.strip() == "":
            label = item_url
        else:
            label = label_input.strip()

        
        active_trackers.append({
            "email": receiver_email,
            "url": item_url,
            "budget": user_budget,
            "label": label
        })

        flash(f"Tracking started! We will email {receiver_email} if it drops below {user_budget} EUR.", "success")
        return redirect(url_for('tracker'))

    
    user_trackers = []
    if current_user != "Guest":
        for t in active_trackers:
            if t['email'] == current_user:
                user_trackers.append(t)

    return render_template('index.html', trackers=user_trackers, current_user=current_user)

@app.route('/delete_tracker', methods=['POST'])
def delete_tracker():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    current_user = session['user_email']
    index_str = request.form.get('tracker_index')
    
    if index_str != None:
        index = int(index_str)

        
        user_trackers = []
        for t in active_trackers:
            if t['email'] == current_user:
                user_trackers.append(t)
                
        if index >= 0 and index < len(user_trackers):
            item_to_delete = user_trackers[index]
            active_trackers.remove(item_to_delete)

    return redirect(url_for('tracker'))

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)