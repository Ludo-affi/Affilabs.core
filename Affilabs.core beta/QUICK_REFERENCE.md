# Quick Reference Card - Hardware Connection

## 🚀 TLDR (Too Long; Didn't Read)

### Power Button
- **Click when GRAY** → Start scan
- **Click when YELLOW** → Cancel scan
- **Click when GREEN** → Disconnect (with confirmation)

### Scan Button (Device Status)
- **Already connected?** → Just reports status, doesn't disconnect ✅
- **Not connected?** → Scans and connects

### Device Types
- **Arduino/PicoP4SPR** = P4SPR
- **PicoP4SPR + RPi** = P4SPR+KNX or ezSPR
- **PicoEZSPR** = P4PRO

---

## 📖 Full Documentation

| Document | What's Inside |
|----------|---------------|
| **START_HERE.md** | Quick overview |
| **README_HARDWARE_BEHAVIOR.md** | **Complete reference** ⭐ |
| **VISUAL_FLOW_GUIDE.md** | State diagrams |
| **DOCUMENTATION_INDEX.md** | All docs listed |

---

## 🆘 Common Questions

**Q: Will scanning disconnect my hardware?**
A: NO. If already connected, it just reports current status.

**Q: Can I cancel a hardware scan?**
A: YES. Click the power button while yellow to cancel.

**Q: Why is the power button stuck yellow?**
A: Click it to cancel. Check backend logs if persists.

**Q: How do I know what device type I have?**
A: It's determined by what's physically plugged in. See Device Status widget.

---

## ⚡ Emergency

**Something broken?** Read `README_HARDWARE_BEHAVIOR.md`
**Need to modify code?** Read `README_HARDWARE_BEHAVIOR.md` FIRST
**Lost?** Start with `DOCUMENTATION_INDEX.md`
