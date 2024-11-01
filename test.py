message = "gyro x,y,z (current/average) = 8.00/-20.22  17.00/89.09  -16.00/-20.17"

# extract just the numbers after the /'s:

# split the message by /:
split_message = message.split('/')
new_values = [float(value.split(' ')[0]) for value in message.split('/')[2:]]

print(new_values)