function rv = mipsver(varargin)
%MIPSVER  Prints or returns MIPS version info for current installation.
%   V = MIPSVER returns the current MIPS version number.
%   V = MIPSVER('all') returns a struct with the fields Name, Version,
%   Release and Date (all strings). Calling MIPSVER without assigning the
%   return value prints the version and release date of the current
%   installation of MIPS.
%
%   See also MPVER.

%   MIPS
%   Copyright (c) 2010-2016 by Power System Engineering Research Center (PSERC)
%   by Ray Zimmerman, PSERC Cornell
%
%   This file is part of MIPS.
%   Covered by the 3-clause BSD License (see LICENSE file for details).
%   See http://www.pserc.cornell.edu/matpower/ for more info.

v = struct( 'Name',     'MIPS', ... 
            'Version',  '1.2.1', ...
            'Release',  '', ...
            'Date',     '01-Jun-2016' );
if nargout > 0
    if nargin > 0
        rv = v;
    else
        rv = v.Version;
    end
else
    fprintf('%-22s Version %-9s  %11s\n', v.Name, v.Version, v.Date);
end