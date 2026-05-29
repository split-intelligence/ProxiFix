from py_vapid import Vapid

# Initialize and generate a new key pair
vapid = Vapid()
vapid.generate_keys()

# 1. To save them as physical .pem files:
vapid.save_key("vapid_private.pem")
vapid.save_public_key("vapid_public.pem")
print("Saved PEM files successfully!")
