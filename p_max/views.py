from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from p_max.models import *
import qrcode
import base64
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

@never_cache
def home(request):
    movies = Movie.objects.all()
    return render(request,'./p_max/home.html',{'movies':movies})


def signUp(request):

    if request.method == "POST":

        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if User.objects.filter(username=username).exists():
            return render(request,'./p_max/signup.html',{
                "error":"Username already exists"
            })

        User.objects.create(
            username=username,
            email=email,
            password=password
        )

        return redirect("login")

    return render(request,"./p_max/signup.html")


def login(request):

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        try:
            user = User.objects.get(username=username,password=password)

            request.session["user-id"] = user.id
            request.session["user-name"] = user.username

            return redirect("dashboard")

        except:
            return render(request,"./p_max/login.html",{
                "error":"Invalid Credentials"
            })

    return render(request,"./p_max/login.html")


@never_cache
def dashboard(request):

    user_id = request.session.get("user-id")

    if not user_id:
        return redirect('login')

    movies = Movie.objects.all()

    return render(request,"./p_max/dashboard.html",{"movies":movies})


def logout(request):
    request.session.flush()
    return redirect('login')


from django.shortcuts import render, redirect, get_object_or_404

def movie_detail(request, movie_id):

    user_id = request.session.get('user-id')

    if not user_id:
        return redirect('login')

    movie = get_object_or_404(Movie, id=movie_id)

    # 👇 Fetch only this movie's shows
    shows = Show.objects.filter(movie=movie)

    reviews = Review.objects.filter(movie=movie)

    if request.method == 'POST':
        comment = request.POST.get('comment')
        rating = request.POST.get('rating')

        user = User.objects.get(id=user_id)

        Review.objects.create(
            movie=movie,
            user=user,
            comment=comment,
            rating=rating
        )

        return redirect(f'/movie_detail/{movie_id}')

    return render(request, "./p_max/movie_detail.html", {
        'movie': movie,
        'shows': shows,
        'reviews': reviews
    })


def book_show(request, show_id):

    user_id = request.session.get('user-id')

    if not user_id:
        return redirect('login')

    show = Show.objects.get(id=show_id)

    rows = ['A','B','C','D','E','F','G','I',"J",'K']
    seats = []
    seats_per_row = 10

    for row in rows:
        for num in range(1, seats_per_row + 1):
            seats.append(row + str(num))

    bookings = Booking.objects.filter(show=show)

    booked_seats = []
    for b in bookings:
        booked_seats.extend(b.seats.split(','))

    if request.method == "POST":

        selected_seat = request.POST.get('selected_seats')

        if not selected_seat:
            return render(request,'./p_max/seat_selection.html',{
                'show': show,
                'booked_seats': booked_seats,
                'seats': seats,
                'error': 'Please select at least one seat'
            })

        seat_list = selected_seat.split(',')

        # ✔ correct price calculation
        seat_count = len(seat_list)
        total_price = seat_count * show.price

        user = User.objects.get(id=user_id)

        Booking.objects.create(
            user=user,
            show=show,
            seats=selected_seat,
            total_price=total_price
        )

        show.avilable_seats -= seat_count
        show.save()

        # save seats for email
        request.session['selected_seats'] = selected_seat

        # send ticket email
        send_mail(request, show_id)

        return render(request,'./p_max/success.html',{
            'show': show,
            'seats': selected_seat,
            'total_price': total_price
        })

    return render(request,'./p_max/seat_selection.html',{
        'show': show,
        'booked_seats': booked_seats,
        'seats': seats
    })

def send_mail(request, show_id):

    user_id = request.session.get('user-id')
    if not user_id:
        return

    user = User.objects.get(id=user_id)
    show = Show.objects.get(id=show_id)

    booking = Booking.objects.filter(user=user, show=show).last()

    seats = booking.seats
    total_price = booking.total_price

    # QR DATA
    qr_data = f"""
Movie: {show.movie.name}
Theatre: {show.theater.name}
Show Time: {show.show_time}
Seats: {seats}
Total Price: ₹{total_price}
User: {user.username}
"""

    qr = qrcode.make(qr_data)

    buffer = BytesIO()
    qr.save(buffer, format="PNG")

    sender = "shivarajgoudapiddanagoudra@gmail.com"
    password = "hfds kjql asio wdkz"
    receiver = user.email

    subject = "🎟 Movie Ticket Confirmation"

    body = f"""
<html>
<body style="font-family:Arial;background:#0b0b0b;padding:30px;color:white;">

<div style="border:1px solid green;max-width:700px;margin:auto;background:#111;border-radius:12px;padding:20px">

<h2 style="color:#00ff9d;text-align:center;">🎬 P MAX MOVIE TICKET</h2>

<table style="width:100%;margin-top:20px;">

<tr>

<td style="width:40%;text-align:center;">
<img src="cid:qrcode" width="200">
<p style="color:#aaa;font-size:12px;">Scan at theatre entry</p>
</td>

<td style="width:60%;padding-left:20px;">

<p>Hello <b>{user.username}</b></p>

<p>Your ticket has been successfully booked.</p>

<p><b>Movie:</b> {show.movie.name}</p>
<p><b>Theatre:</b> {show.theater.name}</p>
<p><b>Show Time:</b> {show.show_time}</p>
<p><b>Seats:</b> {seats}</p>
<p><b>Total Price:</b> ₹{total_price}</p>

</td>

</tr>

</table>

</div>

</body>
</html>
"""

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver

    msg.attach(MIMEText(body, "html"))

    img = MIMEImage(buffer.getvalue())
    img.add_header('Content-ID', '<qrcode>')
    msg.attach(img)

    try:
        server = smtplib.SMTP('smtp.gmail.com',587)
        server.starttls()
        server.login(sender,password)

        server.send_message(msg)
        server.quit()

        print("EMAIL SENT SUCCESSFULLY")

    except Exception as e:
        print("EMAIL ERROR:", e)
