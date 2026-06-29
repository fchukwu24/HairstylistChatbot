# Haircare & appointment assistant


## Install Docker(If it's your first time, you may need a WSL upgrade or something)

## Run the Docker app

## Setup

```
docker compose build --nocache
docker compose up
```

## Open web browser and run link displayed in terminal
## Example interaction

```
Assistant: Hi there! Welcome to our salon. I'm happy to help with haircare advice, salon services, hours, availability, and appointments. How can I assist you today?
User: Hi there, I want tips on my low medium porosity hair for hair care
Assistant: For your low to medium porosity hair, here are some tips:

* Use warm water when washing your hair.
* Use moisturizing shampoo, but only use clarifying shampoo if your hair is greasy.
* Deep condition regularly, letting the deep conditioner sit for 5-10 minutes before rinsing.
* Detangle your hair in sections to prevent breakage.
* Consider using steam treatments to help moisture penetrate your hair.
* Use lightweight products that won't weigh your hair down.
* Consider using products like Aussie Miracle Curls or TGIN Rose Water Smoothing Leave-In Conditioner, which are suggested for low porosity hair.

Remember to be gentle with your hair and avoid using heavy products that can weigh it down.

You: can I book a haircut with Jordan on 2026-06-20?

Assistant: I can help book that. I still need: time, service, customer name.
You: 
Customer name: Frances
Service: Trim
Time: 2 pm
Assistant: I have the appointment details:

- Service: trim
- Stylist: Jordan
- Date: 2026-06-20
- Time: 14:00
- Name: Frances

Please confirm: should I book this appointment?
You: yes
Assistant: You're booked!

- Confirmation ID: 8688blojm724bj51g5h41s3goo
- Service: Trim
- Stylist: Jordan
- Date: 2026-06-20
- Time: 14:00
- Name: Frances
- Email: Not provided
```


