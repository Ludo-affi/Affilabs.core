"""Fix timer completion logic in affilabs_core_ui.py"""
import re

with open('affilabs/affilabs_core_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the timer completion block
# Replace the block from "# Timer completed" to "timer_finished" call
old_pattern = r'''        else:
            # Timer completed
            self\._manual_timer\.stop\(\)
            logger\.info\(f".*Manual timer '\{self\._manual_timer_label\}' completed!"\)

            # Play sound if enabled
            if self\._manual_timer_sound:
                self\._play_timer_sound\(\)

            # Clear timer button
            self\.clear_timer_button\(\)

            # Update pop-out window with finished state
            if hasattr\(self, '_popout_timer'\) and self\._popout_timer and self\._popout_timer\.isVisible\(\):
                self\._popout_timer\.timer_finished\(self\._manual_timer_label\)'''

new_text = '''        else:
            # Timer completed
            self._manual_timer.stop()
            logger.info(f"Manual timer '{self._manual_timer_label}' completed!")

            # Clear timer button
            self.clear_timer_button()

            # Update pop-out window with finished state
            if hasattr(self, '_popout_timer') and self._popout_timer and self._popout_timer.isVisible():
                self._popout_timer.timer_finished(self._manual_timer_label)

            # Start looping alarm sound if enabled
            if self._manual_timer_sound:
                self._start_alarm_loop()'''

result = re.sub(old_pattern, new_text, content, count=1)
if result != content:
    with open('affilabs/affilabs_core_ui.py', 'w', encoding='utf-8') as f:
        f.write(result)
    print("SUCCESS: Timer completion block replaced")
else:
    print("FAILED: Pattern not found, trying line-by-line approach")
    lines = content.split('\n')
    # Find the "# Timer completed" line
    for i, line in enumerate(lines):
        if '# Timer completed' in line:
            print(f"Found at line {i+1}: {repr(line)}")
            # Print surrounding context
            for j in range(max(0,i-2), min(len(lines), i+20)):
                print(f"  {j+1}: {repr(lines[j])}")
            break
