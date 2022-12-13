# What is this

This is a tool to fix the behaviour of tablet mode on HP Spectre x360 laptops
where the 2-in-1's keyboard is disabled when used in laptop form on its side.

In these models the keyboard is disabled based on whether the device is reported
in tablet mode. This is reported by a flag (CVTS) in the PNP0C09 embedded
controller, which independently disables the input devices. This can be
disabled by making the acpi call `HDSM 0` on the device to undo `intel-hid`'s
damage. We make this acpi call using the `acpi_call` kernel module

Re-introducing a software keyboard inhibiting for tablet mode require reading
the iio hinge sensors and setting the input device's inhibit flag when in tablet
mode.

This is basically an incredibly jank python script that should probably be a
kernel module instead.

# Why the name

Because of how unhinged this discovery process has been, and because I read the
hinge sensor hurr durr. I'm not a linux kernel hacker, nor a firmware guru, but
I read that shit and dumped acpi tables just to figure out what was going on
just so I could fix a niche issue.

# How to use

Run `sudo python unhinged.py` or if you use NixOS then you can use the NixOS module provided by the flake.
