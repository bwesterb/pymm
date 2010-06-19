======
PyMM
======

This is a very specific e-mail (de)multiplexer.  It's main use case is to
filter all e-mail for a domain through a single e-mail address.

This script is installed as the handler for all mail on a domain ``pre-domain``
and as the handler of all mail for a single ``post-address``.  An e-mail
handled for ``foo@pre-domain`` is tagged and forwarded to ``filter-address``.
If this tagged e-mail is returned to post-address, it is forwarded to
``foo@target-domain``.

Example: filter all e-mail of a domain through a single GMail account
---------------------------------------------------------------------
(I assume a vpopmail/qmail setup)

Suppose you've got a domain ``mydomain.com`` and you want all e-mail sent to
mydomain.com to be filtered through a single GMail account 
``myfilter@gmail.com``.

Create two new e-mail domains: ``post.mydomain.com`` and ``real.mydomain.com``.
Install ``real.mydomain.com`` as if it was ``mydomain.com``.  Set the
``.qmail-default`` for ``mydomain.com`` to::

   | /path/to/pymm.py pre -f myfilter@gmail.com -t real.mydomain.com -p mydomain.com -P post@post.mydomain.com

Set the ``.qmail-default`` for ``post.mydomain.com`` to::

   | /path/to/pymm.py post -f myfilter@gmail.com -t real.mydomain.com -p mydomain.com -P post@post.mydomain.com

And finally configure ``myfilter@gmail.com`` to forward all e-mail to 
``post@post.mydomain.com`` and you're all set.
