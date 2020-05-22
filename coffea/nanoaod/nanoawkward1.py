import numpy
import awkward1
import uproot


def mixin_class(cls):
    name = cls.__name__
    cls._awkward_mixin = True
    awkward1.behavior[name] = type(name + "Record", (cls, awkward1.Record), {})
    awkward1.behavior["*", name] = type(name + "Array", (cls, awkward1.Array), {})
    possible_inherited = [
        tup for tup in awkward1.behavior if len(tup) >= 2 and callable(tup[0])
    ]
    for tup in possible_inherited:
        for basecls in cls.__mro__[1:]:
            if not hasattr(basecls, "_awkward_mixin"):
                continue
            basename = basecls.__name__
            if len(tup) == 2 and tup[1] == basename:
                signature = (tup[0], name)
                if signature not in awkward1.behavior:
                    awkward1.behavior[signature] = awkward1.behavior[tup]
                break
            elif len(tup) == 3 and basename in tup[1:]:
                if tup[1] == basename:
                    signature = (tup[0], name, tup[2])
                    if signature not in awkward1.behavior:
                        awkward1.behavior[signature] = awkward1.behavior[tup]
                if tup[2] == basename:
                    signature = (tup[0], tup[1], name)
                    if signature not in awkward1.behavior:
                        awkward1.behavior[signature] = awkward1.behavior[tup]
                if tup[1] == basename and tup[2] == basename:
                    signature = (tup[0], name, name)
                    if signature not in awkward1.behavior:
                        awkward1.behavior[signature] = awkward1.behavior[tup]
            # what's still missing: common subtype matching
    return cls


def mixin_method(signatures, transpose=False):
    """Declare a mixin method

    signatures : List[tuple]
        List of (ufunc, type, ...) corresponding to the awkward1 behaviors
    transpose : bool
        Autmatically create a transpose signature (only makes sense for two-argument ufuncs)
    """

    def register(method):
        if transpose:
            mtransposed = lambda left, right: method(right, left)
        for signature in signatures:
            awkward1.behavior[signature] = method
            if transpose:
                if len(signature) != 3:
                    raise RuntimeError(
                        "Not sure how to create transposed method for non-binary signature"
                    )
                if signature[1] == signature[2]:
                    continue
                awkward1.behavior[
                    signature[0], signature[2], signature[1]
                ] = mtransposed
        return method

    return register


@mixin_class
class NanoCollecton:
    @property
    def doc(self):
        return self.layout.purelist_parameter("__doc__")


@mixin_class
class LorentzVector:
    """A cartesian Lorentz vector
    
    Fundamental attributes: x, y, z, t
    """

    @property
    def pt(self):
        return numpy.hypot(self.x, self.y)

    @property
    def eta(self):
        return numpy.arcsinh(self.z / self.pt)

    @property
    def phi(self):
        return numpy.atan2(self.y, self.x)

    @property
    def mass(self):
        return self.t ** 2 - self.p2

    @property
    def p2(self):
        return self.x ** 2 + self.y ** 2 + self.z ** 2

    @property
    def p(self):
        return numpy.sqrt(self.p2)

    @property
    def energy(self):
        return self.t

    @mixin_method(signatures=[(numpy.absolute, "LorentzVector")])
    def abs(self):
        return self.mass

    @mixin_method(signatures=[(numpy.add, "LorentzVector", "LorentzVector")])
    def add(self, other):
        return awkward1.zip(
            {
                "x": self.x + other.x,
                "y": self.y + other.y,
                "z": self.z + other.z,
                "t": self.t + other.t,
            },
            with_name="LorentzVector",
        )

    @mixin_method(signatures=[(numpy.prod, "LorentzVector", "Number")], transpose=True)
    def prod(self, other):
        return awkward1.zip(
            {
                "x": self.x * other,
                "y": self.y * other,
                "z": self.z * other,
                "t": self.t * other,
            },
            with_name="LorentzVector",
        )


@mixin_class
class PtEtaPhiMLorentzVector(LorentzVector, NanoCollecton):
    """A Lorentz vector using pseudorapidity and mass
    
    Fundamental attributes: pt, eta, phi, mass
    """

    @property
    def x(self):
        return self.pt * numpy.cos(self.phi)

    @property
    def y(self):
        return self.pt * numpy.sin(self.phi)

    @property
    def z(self):
        return self.pt * numpy.sinh(self.eta)

    @property
    def t(self):
        return numpy.hypot(self.p, self.mass)

    @property
    def p(self):
        return self.pt * numpy.cosh(self.eta)

    @property
    def pt(self):
        return self["pt"]

    @property
    def eta(self):
        return self["eta"]

    @property
    def phi(self):
        return self["phi"]

    @property
    def mass(self):
        return self["mass"]

    @property
    def p2(self):
        return self.p ** 2

    @property
    def energy(self):
        return self.t

    @mixin_method(
        signatures=[(numpy.prod, "PtEtaPhiMLorentzVector", "Number")], transpose=True
    )
    def prod(self, other):
        return awkward1.zip(
            {
                "pt": self.pt * other,
                "eta": self.eta,
                "phi": self.phi,
                "mass": self.mass * other,
            },
            with_name="PtEtaPhiMLorentzVector",
        )


@mixin_class
class Candidate(LorentzVector):
    """A Lorentz vector with charge

    Fundamental properties: x, y, z, t, charge
    """

    @mixin_method(signatures=[(numpy.add, "Candidate", "Candidate")])
    def add(self, other):
        return awkward1.zip(
            {
                "x": self.x + other.x,
                "y": self.y + other.y,
                "z": self.z + other.z,
                "t": self.t + other.t,
                "charge": self.charge + other.charge,
            },
            with_name="Candidate",
        )


@mixin_class
class PtEtaPhiMCandidate(PtEtaPhiMLorentzVector):
    """A Lorentz vector in eta, mass coordinates with charge

    Fundamental properties: pt, eta, phi, mass, charge
    """

    @mixin_method(
        signatures=[
            (numpy.add, "PtEtaPhiMCandidate", "PtEtaPhiMCandidate"),
            (numpy.add, "PtEtaPhiMCandidate", "Candidate"),
        ]
    )
    def add(self, other):
        return awkward1.zip(
            {
                "x": self.x + other.x,
                "y": self.y + other.y,
                "z": self.z + other.z,
                "t": self.t + other.t,
                "charge": self.charge + other.charge,
            },
            with_name="Candidate",
        )


@mixin_class
class Photon(PtEtaPhiMCandidate):
    @property
    def mass(self):
        return 0.0


def _with_length(array: awkward1.layout.VirtualArray, length: int):
    return awkward1.layout.VirtualArray(
        array.generator.with_length(length),
        array.cache,
        array.cache_key,
        array.identities,
        array.parameters,
    )


class NanoEventsFactory:
    default_mixins = {
        "Electron": "PtEtaPhiMCandidate",
        "Photon": "Photon",
        "Muon": "PtEtaPhiMCandidate",
        "Tau": "PtEtaPhiMCandidate",
        "Jet": "PtEtaPhiMLorentzVector",
        "FatJet": "PtEtaPhiMLorentzVector",
    }

    def __init__(
        self,
        file,
        treename="Events",
        entrystart=None,
        entrystop=None,
        cache=None,
        mixin_map=None,
        metadata=None,
    ):
        if not isinstance(file, uproot.rootio.ROOTDirectory):
            file = uproot.open(file)
        self._tree = file[treename]
        self._entrystart, self._entrystop = uproot.tree._normalize_entrystartstop(
            self._tree.numentries, entrystart, entrystop
        )
        self._keyprefix = "/".join(
            [
                file._context.uuid.hex(),
                treename,
                str(self._entrystart),
                str(self._entrystop),
            ]
        )

        if cache is None:
            cache = awkward1.layout.ArrayCache({})
        else:
            cache = awkward1.layout.ArrayCache(cache)
        self._cache = cache

        self._mixin_map = {}
        self._mixin_map.update(self.default_mixins)
        if mixin_map is not None:
            self._mixin_map.update(mixin_map)

        self._metadata = metadata  # TODO: JSON only?
        self._branches_read = set()

    def __len__(self):
        return self._entrystop - self._entrystart

    def reader(self, branch_name):
        self._branches_read.add(branch_name)
        return awkward1.layout.NumpyArray(
            self._tree[branch_name].array(
                entrystart=self._entrystart, entrystop=self._entrystop, flatten=True
            )
        )

    def _array(self, branch_name: bytes):
        interpretation = uproot.interpret(self._tree[branch_name])
        if isinstance(interpretation, uproot.asjagged):
            dtype = interpretation.content.type
            length = None
        else:
            dtype = interpretation.type
            length = len(self)
        form = awkward1.forms.Form.fromjson('"%s"' % dtype)
        generator = awkward1.layout.ArrayGenerator(
            self.reader, (branch_name,), {}, form=form, length=length,
        )
        return awkward1.layout.VirtualArray(
            generator,
            self._cache,
            cache_key="/".join([self._keyprefix, "file", branch_name.decode("ascii")]),
            parameters={"__doc__": self._tree[branch_name].title.decode("ascii"),},
        )

    def _listarray(self, counts, content, recordparams):
        offsets = awkward1.layout.Index32(
            numpy.concatenate([[0], numpy.cumsum(counts)])
        )
        length = offsets[-1]
        return awkward1.layout.ListOffsetArray32(
            offsets,
            awkward1.layout.RecordArray(
                {k: _with_length(v, length) for k, v in content.items()},
                parameters=recordparams,
            ),
        )

    def events(self):
        arrays = {}
        for branch_name in self._tree.keys():
            arrays[branch_name.decode("ascii")] = self._array(branch_name)

        # parse into high-level records (collections, list collections, and singletons)
        collections = set(k.split("_")[0] for k in arrays)
        collections -= set(
            k for k in collections if k.startswith("n") and k[1:] in collections
        )

        def collectionfactory(name):
            mixin = self._mixin_map.get(name, None)
            if "n" + name in arrays:
                # list collection
                cname = "n" + name
                counts = arrays[cname]
                content = {
                    k[len(cname) :]: arrays[k]
                    for k in arrays
                    if k.startswith(name + "_")
                }
                recordparams = {
                    "__doc__": counts.parameters["__doc__"],
                    "__record__": mixin,
                }
                form = awkward1.forms.ListOffsetForm(
                    "i32",
                    awkward1.forms.RecordForm(
                        {k: v.form for k, v in content.items()}, parameters=recordparams
                    ),
                )
                generator = awkward1.layout.ArrayGenerator(
                    self._listarray,
                    (counts, content, recordparams),
                    {},
                    form=form,
                    length=len(self),
                )
                return awkward1.layout.VirtualArray(
                    generator,
                    self._cache,
                    cache_key="/".join([self._keyprefix, "file", name]),
                    parameters=recordparams,
                )
            elif name in arrays:
                # singleton
                return arrays[name]
            else:
                # simple collection
                return awkward1.layout.RecordArray(
                    {
                        k[len(name) + 1 :]: arrays[k]
                        for k in arrays
                        if k.startswith(name + "_")
                    },
                    parameters={"__record__": mixin,},
                )

        events = awkward1.layout.RecordArray(
            {name: collectionfactory(name) for name in collections},
            parameters={"metadata": self._metadata},
        )

        return awkward1.Array(events)