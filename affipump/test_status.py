from affipump_controller import AffipumpController

c = AffipumpController()
c.open()
s = c.get_status(1)
e = c.get_error_code(1)

print(f"Status byte: 0x{s['status']:02x}")
print(f"Busy: {s['busy']}")
print(f"Idle: {s['idle']}")
print(f"Error: {s['error']}")
print(f"Initialized: {s['initialized']}")
print(f"Error code: {e}")

c.close()
