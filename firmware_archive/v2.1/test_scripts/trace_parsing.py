"""
Trace the parsing logic to see what values would be extracted
"""

command = "rankbatch:100,150,200,250,1000,100,10\n"
print(f"Command: {repr(command)}")
print(f"Length: {len(command)}")
print()

# Initialize arrays (C initializes with null bytes, not '0' chars)
str_int_a = ['\0'] * 4
str_int_b = ['\0'] * 4
str_int_c = ['\0'] * 4
str_int_d = ['\0'] * 4
str_settling = ['\0'] * 5
str_dark = ['\0'] * 5
str_cycles = ['\0'] * 5

field = 0
field_pos = 0
pos = 10  # Start after "rankbatch:"

print(f"Starting parse at position {pos}")
print()

while pos < 48 and command[pos] != '\0' and command[pos] != '\n':
    ch = command[pos]
    print(f"pos={pos:2d} ch={repr(ch)} field={field} field_pos={field_pos}", end="")

    if command[pos] == ',':
        print(f" → COMMA: field++")
        field += 1
        field_pos = 0
    elif command[pos] >= '0' and command[pos] <= '9':
        if field == 0 and field_pos < 3:
            str_int_a[field_pos] = command[pos]
            print(f" → str_int_a[{field_pos}] = '{command[pos]}'")
            field_pos += 1
        elif field == 1 and field_pos < 3:
            str_int_b[field_pos] = command[pos]
            print(f" → str_int_b[{field_pos}] = '{command[pos]}'")
            field_pos += 1
        elif field == 2 and field_pos < 3:
            str_int_c[field_pos] = command[pos]
            print(f" → str_int_c[{field_pos}] = '{command[pos]}'")
            field_pos += 1
        elif field == 3 and field_pos < 3:
            str_int_d[field_pos] = command[pos]
            print(f" → str_int_d[{field_pos}] = '{command[pos]}'")
            field_pos += 1
        elif field == 4 and field_pos < 4:
            str_settling[field_pos] = command[pos]
            print(f" → str_settling[{field_pos}] = '{command[pos]}'")
            field_pos += 1
        elif field == 5 and field_pos < 4:
            str_dark[field_pos] = command[pos]
            print(f" → str_dark[{field_pos}] = '{command[pos]}'")
            field_pos += 1
        elif field == 6 and field_pos < 4:
            str_cycles[field_pos] = command[pos]
            print(f" → str_cycles[{field_pos}] = '{command[pos]}'")
            field_pos += 1
        else:
            print(f" → DROPPED (field={field}, field_pos={field_pos})")
    else:
        print(f" → IGNORED")

    pos += 1

print()
print("="*70)
print("Final strings (null-terminated):")
str_int_a_s = ''.join(str_int_a).split('\0')[0]
str_int_b_s = ''.join(str_int_b).split('\0')[0]
str_int_c_s = ''.join(str_int_c).split('\0')[0]
str_int_d_s = ''.join(str_int_d).split('\0')[0]
str_settling_s = ''.join(str_settling).split('\0')[0]
str_dark_s = ''.join(str_dark).split('\0')[0]
str_cycles_s = ''.join(str_cycles).split('\0')[0]

print(f"str_int_a    = '{str_int_a_s}'")
print(f"str_int_b    = '{str_int_b_s}'")
print(f"str_int_c    = '{str_int_c_s}'")
print(f"str_int_d    = '{str_int_d_s}'")
print(f"str_settling = '{str_settling_s}'")
print(f"str_dark     = '{str_dark_s}'")
print(f"str_cycles   = '{str_cycles_s}'")
print()
print("Converted values (atoi simulation):")
print(f"int_a = {int(str_int_a_s) if str_int_a_s else 0}")
print(f"int_b = {int(str_int_b_s) if str_int_b_s else 0}")
print(f"int_c = {int(str_int_c_s) if str_int_c_s else 0}")
print(f"int_d = {int(str_int_d_s) if str_int_d_s else 0}")
print(f"settling_ms = {int(str_settling_s) if str_settling_s else 0}")
print(f"dark_ms = {int(str_dark_s) if str_dark_s else 0}")
num_cycles = int(str_cycles_s) if str_cycles_s else 0
print(f"num_cycles = {num_cycles} (from '{str_cycles_s}')")

if num_cycles < 1:
    num_cycles = 1
    print(f"num_cycles clamped to: {num_cycles}")
