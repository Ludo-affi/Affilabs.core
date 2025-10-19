# OEM Quick Reference Card

## 🔐 Default Access Credentials

```
Password: Affinite2025
```

**Change this password immediately in production!**

---

## 🚀 Quick Start

### Access OEM Service Mode

1. **Open Device Configuration:**
   ```bash
   python -m widgets.device_settings
   ```

2. **Click:** `🔓 Unlock OEM Mode` button

3. **Enter Password:** `Affinite2025`

4. **Make Changes:** All settings now unlocked

5. **Lock When Done:** Click `🔒 Lock OEM Mode`

---

## ⏱️ Session Info

- **Timeout:** 30 minutes
- **Auto-Lock:** Yes (after timeout)
- **Password:** Required for each session

---

## 🔧 What You Can Modify (OEM Mode)

✅ Optical Fiber Diameter (100/200 µm)
✅ LED PCB Model (Luminus/OSRAM)
✅ Hardware Detection & Updates
✅ Timing Parameters
✅ Factory Reset

---

## 🔒 Security Files

**Config:** `C:\Users\<user>\ezControl\config\security.json`
**Audit Log:** `C:\Users\<user>\ezControl\config\access_audit.log`

---

## 🔑 Change Password

```python
from utils.security import get_security_manager

security = get_security_manager()
success, msg = security.change_password(
    old_password="Affinite2025",
    new_password="NewPassword123!"
)
```

---

## 🆘 Password Reset (Emergency)

```bash
# Delete security file to restore default
del C:\Users\<user>\ezControl\config\security.json

# Restart application - default password active
```

---

## 📞 Support Contact

**Affinite Instruments**
support@affinite.com
OEM Hotline: (XXX) XXX-XXXX

---

**Remember:** Keep OEM password secure and change from default!
