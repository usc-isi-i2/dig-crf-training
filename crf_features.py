#!/usr/bin/env python
import re
import string
from sys import stdin,stdout,stderr
import inspect
import codecs
from argparse import ArgumentParser

scriptArgs = ArgumentParser(description="Extracts features for input to CRF++'s crf_learn and crf_test executables")

scriptArgs.add_argument('--input',help="Optional input file, with one token per line. Additional tab-separated fields, e.g. a label, may follow. Reads from stdin if no argument provided.")
scriptArgs.add_argument('--output',help="Optional output file with lines of the form '<token><tab><feat><tab<feat><tab>...<label>'. Writes to stdout if no argument provided.")
scriptArgs.add_argument('--featlist',help="Required input file with features to be extracted, one feature entry per line.",required=True)
scriptArgs.add_argument('--templates',help="Optional output file containing feature template definitions needed by crf_learn")
scriptArgs.add_argument('--labeled',action='store_true',help="Require input lines to have a label as well as a token.")
scriptArgs.add_argument('--monocase',action='store_true',help="Convert all input tokens to lower case before feature extraction.")
scriptArgs.add_argument('--verbose',action='store_true',help="Print out extra information about the feature extraction.")
scriptArgs.add_argument('--extrafeatdefs',help="File of additional 'defFeat' feature definitions to use.")

        
argValues = vars(scriptArgs.parse_args())


# Command line arguments


inputFile    = argValues["input"]
outputFile   = argValues["output"]
featListFile = argValues["featlist"]
templateFile = argValues["templates"]
labeled      = argValues["labeled"]
verbose      = argValues["verbose"]
monocase     = argValues["monocase"]
featDefsFile = argValues["extrafeatdefs"]


# Mapping from feature names to FeatDefinition objects.

featureNamesToDefinitions = {}

# The list of specific features and their associated functions that that will be used in the current run of the program.

featureEntries         = []  # Entries in the feature list file.
featureNamesUsed       = []  # Column names of the feature matrix.
featureDefinitionsUsed = []  # Corresponding feature definitions of those columns.

# Constant that is used to denote null aka missing aka empty feature value

EMPTY = "_NULL_"

# Other stuff

VOWELS           = set("a e i o u A E I O U".split())

cvdTranslation   = None  # Gets initialized by function
shapeTranslation = None



# Features inspired by:
#  - Zhang and Johnson (2003) [http://stat.rutgers.edu/home/tzhang/papers/conll03-rrm.pdf]
#  - Ratinov and Roth (2009) [http://l2r.cs.uiuc.edu/~danr/Papers/RatinovRo09.pdf]



########################################################################################################################################


def main ():
    """The function that is called in a command line context. """
    # Make sure we aren't unintentionally overwriting an input file        
    nonOverlapping([featListFile,inputFile,featDefsFile],[outputFile,templateFile])
    # Initialize whatever script variables have to be initialized
    initializeScriptData()
    # Define the script's built-in features
    defineBuiltInFeatures()   
    # Read any additional feature definitions that may have been specified
    if (featDefsFile):
        readExtraFeatDefsFile(featDefsFile)
    # Read the list of feature entries we will be working with
    readFeatureListFile(featListFile)
    # Print them out if we are in 'verbose' mode.
    if (verbose):
        printFeatsUsed()
    # Featurize the file.            
    writeFeatMatrixFile(inputFile,outputFile,labeled)
    # Write out the template file if a template file argument was provided.
    if (templateFile):
        writeTemplateFile(templateFile)
    
def initializeScriptData ():
    global cvdTranslation,shapeTranslation
    cvdTranslation   = makeCVDTranslation()
    shapeTranslation = makeShapeTranslation()
    
# TODO: Do we still need access outside of the command line?
# def OLDextractFeatures (inputFile, outputFile, featListFile,templateFile=None,labeled=False,featDefsFile=None):
#     """The top-level function that does the work.  This is useful for being called by other scripts in a 
#        programmatic context where command-line argument parsing can be dispensed with."""
#     # Read any additional feature definitions that may have been specified
#     if (featDefsFile):
#         readExtraFeatDefsFile(featDefsFile)
#     # Get the features we will be working with
#     readFeatureListFile(featListFile)
#     # Print them out
#     printFeatsUsed()
#     # Featurize the file.            
#     writeFeatMatrixFile(inputFile,outputFile,labeled)
#     # Write the template file if one was provided.
#     if (templateFile):
#         writeTemplateFile(templateFile)


def writeFeatMatrixFile (inputFile,outputFile,labeled):
    """Featurizes inputFile, writing the result to outputFile.  If 'labeled' is True, lines in the inputFile must have a label. """
    reqFields = None
    instream  = codecs.open(inputFile,encoding="utf-8",mode="rb") if inputFile != None else stdin 
    outstream = codecs.open(outputFile,encoding="utf-8",mode="wb") if outputFile != None else stdout
    tokens  = []
    labels = []
    lineNum = 1
    while (True):
        line = instream.readline()
        if (not line):
            break
        line = line.strip()
        if (line == ""):
            featuresPerWord = featurizeSentence(tokens)
            for i in range(0,len(tokens)):
                outfields = [tokens[i]]
                outfields.extend(featuresPerWord[i])
                outfields.extend(labels[i])
                # outstream.write("%s\n" % join(outfields,"\t"))
                outstream.write("%s\n" % "\t".join(outfields))
            outstream.write("\n")
            outstream.flush()
            tokens = []
            labels = []
        else:
            # Extract fields; check validity and consistency of line format
            fields  = line.split("\t")
            nfields = len(fields)
            if (reqFields == None):
                if (labeled and nfields < 2):
                    raise RuntimeError("Label is required but missing")
                reqFields = nfields
            elif (nfields != reqFields):
                raise RuntimeError(format("Inconsistent number of fields in line %d: current line is %d vs. previous lines %d" % (lineNum,nfields,reqFields)))
            token = unicode(fields[0])
            if (monocase):
                token = token.lower()
            tokens.append(token)
            labels.append(fields[1:])
        lineNum += 1
    if (tokens): # I could take care of this but I won't. Discipline. ;)
        raise RuntimeError("Input file did not end with an empty line as required")
    if (inputFile != None):
        instream.close()     
    if (outputFile != None):
        outstream.close()  

def featurizeSentence (tokens):
    """Takes a list of tokens, and returns a corresponding list of feature values"""
    columnsPerFeature = []
    for featDef in featureDefinitionsUsed:
        column = featDef.sequenceFunc(tokens)
        for i,val in enumerate(column):
            if (val == None):
                column[i] = EMPTY
        columnsPerFeature.append(column)
    rowsPerToken = []
    for i in range(0,len(tokens)):
        row = []
        for column in columnsPerFeature:
            row.append(column[i])
        rowsPerToken.append(row)
    return rowsPerToken

def readExtraFeatDefsFile (filename):
    stderr.write("Reading additional feature defs from %s\n" % filename)
    execfile(filename,globals(),locals())


def composeTokenFunctions (func1,func2):
    """Takes two token functions; returns the token function defined as func2(func1(x)). """
    return lambda token : func2(getFeatVal(func1,token))

def getPhraseIndexFeatValues (tokens,phraseIndex):
    """Feature looks at the whole utterance and returns a vector of true/false feature values, one feature value per word"""
    featValues = [None] * len(tokens)
    for i in range(0,len(tokens)):
        phrase = getMatchingPhrase(tokens,i,phraseIndex)
        if (phrase):
            for j in range(0,len(phrase)):
                featValues[i+j] = "true"
    for i,val in enumerate(featValues):
        if (val == None):
            featValues[i] = "false"
    return featValues
    
def getMatchingPhrase (tokens,idx,phraseIndex):
    """Returns the matching phrase from phraseIndex at position idx in tokens. Returns None if there is no match."""
    token     = tokens[idx].lower()
    phrases   = phraseIndex.get(token)
    if (phrases):
        remaining = len(tokens) - idx
        for phrase in phrases:
            if (remaining >= len(phrase) and matches(tokens,idx,phrase)):
                return phrase
    return None

def matches (tokens,idx,phrase):
    """Returns True if phrase is present at position idx in tokens"""
    for i,word in enumerate(phrase):
        if (tokens[idx+i].lower() != word):
            return False
    return True

def wordSetToTokenFunc (wordSet):
    """Takes a set of words and returns a token-level function that returns true if the 
       token is in that set of words."""
    return lambda token : token.lower() in wordSet

def phraseIndexToSequenceFunc (phraseIndex):
    return lambda tokens : getPhraseIndexFeatValues(tokens,phraseIndex)

def tokenFuncToSequenceFunc (tokenFunc):
    """Takes a function that takes a single token as argument, and and lifts it to a function 
       that takes a sequence of tokens as argument.""" 
    return lambda tokens : [getFeatVal(tokenFunc,token) for token in tokens]


def executeOptionsDirective (string):
    global monocase
    string = string.lower()
    string = re.sub(r'^options:','',string)
    tokens = string.split()
    for token in tokens:
        if (token == "monocase"):
            # print "\nSetting monocase to True"
            monocase = True
        else:
            raise RuntimeError(format("Unknown token in params: command: %s" % token))

def executeDefWordList (string):
    """Executes a feature definition that defines the feature by membership in a set of words 
       specified by a comma-delimited list of files"""
    tokens    = string.split()
    featname  = tokens[1]
    filenames = tokens[2]
    wordSet   = readWordSetFromFiles(filenames.split(","))
    tokenFunc = wordSetToTokenFunc(wordSet)
    defFeat(featname,tokenFunc)
    
def executeDefPhraseList (string):
    """Executes a feature definition that defines the feature by whole-phrase match in a phrase
       list specified by a comma-delimited list of files"""
    tokens    = string.split()
    featname  = tokens[1]
    filenames = tokens[2]
    index     = readPhraseIndexFromFiles(filenames.split(","))
    seqFunc   = phraseIndexToSequenceFunc(index)
    defFeat(featname,seqFunc,isSeq=True)
    

def defFeat (name,func,isSeq=False):
    """Defines a feature in terms of a name and a value-extraction function.  By default, the function is interpreted as 
       operating on tokens, and returning a single feature value for them.  If isSeq is true, the function is interpreted 
       as operating on an entire word sequence and returning a entire sequence of values of the same length. """     
    assert(name)
    assert(func)
    if (" " in name or "\t" in name):  # Probaby this would never happen, but may as well prevent it!
        raise RuntimeError(format("Can't have whitespace in feature name: '%s'" % name))
    if (featureNamesToDefinitions.get(name)):
        stderr.write("\n\nREDEFINING FEATURE: %s\n\n" % name)
    featDef            = FeatDefinition(name)
    featDef.isSequence = isSeq
    if (featDef.isSequence):
        featDef.tokenFunc    = None
        featDef.sequenceFunc = func
    else:
        featDef.tokenFunc    = func
        featDef.sequenceFunc = tokenFuncToSequenceFunc(func)
    # Don't forget to set the featname's definition in the map
    featureNamesToDefinitions[name] = featDef
    return featDef


def readFeatureListFile (filename):
    """Reads the features to be used, one feature entry per line.  Lines starting with '#' are treated as comments and ignored. Feature entries
       may be simple, consisting of just a single feature reference, or compound, consisting of multiple feature references separated by '/'s. """
    with open(filename,"r") as instream:
        for line in instream:
            line = line.strip()
            # Ignore blank lines or lines starting with a '#'.
            if (line == "" or line.startswith("#")):  
                pass
            # Special forms like 'defwordlist' of 'defphraselist'
            elif (line.lower().startswith("defwordlist")):
                executeDefWordList(line)
            elif (line.lower().startswith("defphraselist")):
                executeDefPhraseList(line)
            elif (line.lower().startswith("options:")):
                executeOptionsDirective(line)
            # Otherwise treat as regular feature entry
            else:
                featureEntries.append(parseFeatureListEntry(line))    
    # Get the set of feature names for which we have a simple (non-compound) entry.
    singleFeats = set() 
    for entry in featureEntries:
        if (len(entry.featRefs) == 1):
            singleFeats.add(entry.featRefs[0].feat)
    # For compound entries, add simple feature entries for component features not explicitly provided.
    featsToAdd = []
    for entry in featureEntries:
        for featRef in entry.featRefs:
            featname = featRef.feat
            if (featname not in singleFeats and featname not in featsToAdd):
                featsToAdd.append(featname)
    # Just treat feature entries to be added as strings to be parsed 
    for featname in featsToAdd:
        featureEntries.append(parseFeatureListEntry(featname))
    # Set up the lists of single-feature names and defintions that are being used in this run of the feature extractor. 
    # This gives the semantics of the columns in the feature matrix file. 
    for entry in featureEntries:        
        if (len(entry.featRefs) == 1):
            featName = entry.featRefs[0].feat
            featureNamesUsed.append(featName)
            featureDefinitionsUsed.append(getFeatDefinitionOrError(featName))


def parseFeatureListEntry (entryString):
    """Parses a line from the feature list file, and returns the corresponding FeatListEntry object."""
    entry       = FeatListEntry()    
    tokens      = entryString.split()
    refString   = tokens[0]
    quantTokens = tokens[1:]
    # The entry is U: or B: followed by feature names
    prefixUorB  = re.search(r"^(U|B):(\S*)",refString)
    if (prefixUorB):
        entry.type = prefixUorB.group(1)
        refString  = prefixUorB.group(2)
    # The entry is just U or B on its own
    elif (refString == "B" or refString == "U"):
        entry.type = refString
        refString  = ""      
    # Parse each FeatRef in the entry. If there is more than one, they are separated by '/'. 
    for featRef in split(refString,"/"):
        entry.featRefs.append(parseFeatRef(featRef))
    # Parse the quantifier string, which specifies which positions the entry will apply to
    parseQuantifierString(entry,join(quantTokens))    
    return entry    


def parseQuantifierString (featListEntry,quantString):
    """Takes a FeatListEntry and the 'quantifier' portion of the feat list entry string. This string specifies the set of word positions the entry 
       is to be applied to, and whether they are to be treated bag-of-words are not.  An empty quantifier string is implicitly position 0 only. 
       Multiple position specifications are allowed, and combined via set union."""
    unparsed  = quantString.strip()
    positions = set()
    while (unparsed != ""):
        # Window:  +- 2    
        plusMinus = re.match(r'\+-\s*(\d+)',unparsed)
        # Range: -2...2 or -1..2
        ellipsis  = re.match(r'([+-]?\d+)\s?\.\.\.?\s?([+-]?\d+)',unparsed)       
        # Comma-delimited list of positions: -1,1,+2
        commas = re.match(r'([+-]?\d+)((,[+-]?\d+)*)',unparsed)
        # Bag-of-words spec:  -bow
        bow       = re.match(r'\-bow',unparsed)
        if (plusMinus):
            window = int(plusMinus.group(1))
            end    = plusMinus.end()
            positions.update(range(-1*window,window+1))            
            unparsed = unparsed[end:].strip()
        elif (ellipsis):            
            first = int(ellipsis.group(1))
            last  = int(ellipsis.group(2))
            end   = ellipsis.end()
            if (first > last):
                raise RuntimeError("Last %d is before first %d in this quantifier quantString: %s" % (last,first,quantString))
            positions.update(range(first,last+1))
            unparsed = unparsed[end:].strip()
        elif (bow):
            end = bow.end()
            featListEntry.bow = True
            unparsed = unparsed[end:].strip()
        elif (commas):
            pos1   = commas.group(1)
            others = split(commas.group(2),",")
            positions.add(int(pos1))
            for other in others:
                positions.add(int(other))
            end = commas.end()
            unparsed = unparsed[end:].strip()
        else:
            raise RuntimeError(format("Can't parse '%s' in %s" % (unparsed,quantString)))
    if (not positions):
        positions.add(0)
    featListEntry.positions = list(positions) 
    featListEntry.positions.sort()            
                   


def parseFeatRef (featRefString):
    """Parses a single feature reference like 'cvd' or 'cvd-1' into a FeatRef object"""
    assert(featRefString)
    if (isDefinedFeat(featRefString)):
        return FeatRef(featRefString)
    else:
        # Check whether it has a +n or -n relative position indicator
        relPos = re.search(r"^(\S+)([+-]\d+)$",featRefString)
        if (relPos):
            featname = relPos.group(1)
            pos      = int(relPos.group(2))      
            getFeatDefinitionOrError(featname)
            return FeatRef(featname,pos)       
        else:
            getFeatDefinitionOrError(featRefString)
            return FeatRef(featRefString)


def readWordSetFromFiles (filenames):
    words = set()
    for filename in filenames:
        readWordSet(filename,words)
    return words

def readWordSet (filename,words):
    instream = codecs.open(filename,"r","utf-8")
    for line in instream:
        line = line.strip()
        line = line.lower()
        if (line != "" and not line.startswith("#")):
            for word in line.split():
                words.add(word)
    instream.close()

def readPhraseIndexFromFiles (filenames):
    """Takes a list of files; reads phrases from them, with one phrase per line, ignoring blank lines 
       and lines starting with '#'. Returns a map from words to the list of phrases they are the first word of."""
    phraseIndex = dict()
    for filename in filenames:
        with open(filename,"r") as instream:
            for line in instream:
                line = line.strip()
                if (line != "" and not line.startswith("#")):
                    line   = line.lower()
                    phrase = line.split()
                    firstWord  = phrase[0]
                    phraseList = phraseIndex.get(firstWord)
                    if (phraseList == None):
                        phraseList = []
                        phraseIndex[firstWord] = phraseList
                    phraseList.append(phrase)
    # Sort each list of phrases in decreasing order of phrase length
    for phrases in phraseIndex.values():
        phrases.sort(key=lambda p: len(p),reverse=True)
    return phraseIndex

def isDefinedFeat (string):
    """Returns true if the string is the name of an existing defined feature."""
    return featureNamesToDefinitions.get(string) != None

def writeTemplateFile (filename):
    "Writes out the template definitions in the index-addressed format that CRF++ uses."
    # We split up unigram and bigram features, and write their template entries separately just for clarity's sake.
    unigrams = []
    bigrams  = []
    for entry in featureEntries:
        if (entry.type == "B"):
            bigrams.append(entry)
        else:
            unigrams.append(entry)
    outstream = open(filename,"wb")
    writeTemplatesForFeatEntries(unigrams,outstream)
    # We typically would not expect a bigram feature except for "B" itself, but they are allowed w/o prejudice.
    if (bigrams):
        outstream.write("\n")
        writeTemplatesForFeatEntries(bigrams,outstream)
    outstream.close()

def writeTemplatesForFeatEntries (entries,outstream):
    "Writes a list of FeatListEntry objects to a stream, leaving the stream open when it is done"
    idx = 0
    for entry in entries:
        # An entry containing no feature references is just a reference to a tag unigram or tag bigram, and 
        # produces 'U' or 'B' on its own line 
        if (len(entry.featRefs) == 0):
            outstream.write("%s\n" % entry.type)
        # Otherwise, we write out the entries with ids that serve to distinguish them from one another. These ids
        # are just strings whose content doesn't matter, so long as they are distinguishing. 
        else:
            # The main part of the id is just the type U or B, together with a zero-padded index
            entryId = entry.type + format("%02d" % idx)
            for pos in entry.positions:
                outstream.write(entryId)
                # Add a +n or -n to distinguish different values of pos, unless this entry is bag-of-words
                if (not entry.bow):
                    outstream.write("+" if pos >= 0 else "")
                    outstream.write(str(pos))
                outstream.write(":")
                for f,ref in enumerate(entry.featRefs):
                    # The column index is i+1, since index 0 in feature matrix rows is by convention the token itself. We don't have
                    # to write the token out, but we do for clarity. If the token is used as a feat itself, it will simply appear twice.
                    col = featureNamesUsed.index(ref.feat) + 1
                    row = ref.pos + pos                   
                    if (f > 0):
                        outstream.write("/")
                    # Each indexed feature reference is of the form %x[i,j].  During CRF++ internal feature expansion, 
                    # these strings get replaced with the corresponding string value in the feature matrix.
                    outstream.write("%x" + format("[%d,%d]" % (row,col)))
                outstream.write("\n")
            idx += 1



def printFeatsUsed ():
    """Prints out the feature names which define the columns of the feature matrix."""
    stderr.write("\nColumns of feature matrix:\n\n")
    for i,feat in enumerate(featureNamesUsed):
        stderr.write("%-2d  %s\n" % (i+1,feat))


def getFeatFunc (feat):
    "Returns the definition function for the feature"
    return getFeatDefinitionOrError(feat).tokenFunc


def getPrefixSuffixTokenFunc (prefixSuffix,tokenFunc,n):
    "Takes a prefix or suffix indicator, an existing token func, and an integer."
    if (prefixSuffix == "prefix"):
        return lambda token :  prefix(getFeatVal(tokenFunc,token),n)
    elif (prefixSuffix == "suffix"):
        return lambda token :  suffix(getFeatVal(tokenFunc,token),n)
    else:
        raise RuntimeError(format("Value given to prefixSuffix arg is neither 'prefix' nor 'suffix': %s" % prefixSuffix))

def getFeatDefinitionOrError (featname):
    """Returns the stored definition for feature, constructing a definition via function composition
       if the name it contains '.'.  Error if there is no feature, or none can be constructed."""
    entry = featureNamesToDefinitions.get(featname)
    if (entry):
        return entry
    elif ("." in featname):
        return defineFeatureUsingFunctionComposition(featname)
    else:
        raise RuntimeError(format("Undefined feature: '%s'" % featname))

def defineFeatureUsingFunctionComposition (featstring):
    """Takes a string like containing ".", which indicates function composition.  The first '.'-separated token is an
       existing feature, to whose values the functions represented by subsequent elements are successively applied.
       Example: 'cvd.upper.prefix3', which starts with 'cvd' as base feature, and takes the upper case version, and then 
       3-character prefix."""
    tokens = featstring.split(".")
    underlyingFeat = tokens[0]
    underlyingDef  = getFeatDefinitionOrError(underlyingFeat)
    tokenFunc      = underlyingDef.tokenFunc
    for i in range(1,len(tokens)):
        token = tokens[i]
        # If it is a form like 'prefix2' or 'suffix4'..
        affixMatch = re.search(r'^(prefix|suffix)(\d+)$',token)
        if (affixMatch):
            prefixSuffix = affixMatch.group(1)
            n            = int(affixMatch.group(2))
            tokenFunc = getPrefixSuffixTokenFunc(prefixSuffix,tokenFunc,n)       
        elif (token == "unique"):
            tokenFunc = composeTokenFunctions(tokenFunc,uniqueChars)
        elif (token == "sort"):
            tokenFunc = composeTokenFunctions(tokenFunc,sortChars)
        elif (isFunction(token)):
            func      = globals()[token]
            tokenFunc = composeTokenFunctions(tokenFunc,func)
        else:
            raise RuntimeError(format("Can't handle this token: %s" % token))
    return defFeat(featstring,tokenFunc)

def isFunction (tok):
    """Takes a string; returns true if the string is the name of a function."""
    bindings = globals().get(tok)
    return (bindings != None and inspect.isroutine(bindings))

def upcase (tok):
    """Takes a token; returns its uppercase version.""" 
    return tok.upper()

def downcase (tok):
    """Takes a token; returns its lowercase version.""" 
    return tok.lower()

def prefix (s, n):
    "Returns the n-element prefix of s, or EMPTY if s is not long enough."
    length = len(s)
    if (length >= n):
        return s[0:n]
    else:
        return EMPTY

def suffix (s, n):
    "Returns the n-element suffix of s, or EMPTY if s is not long enough"
    length = len(s)
    if (length >= n):
        return s[length-n:length]
    else:
        return EMPTY    


def cvd (tok):
    """Maps upper/lowercase vowels to V/v, upper/lowercase consonants to C/c, and digits to D"""
    result = tok.translate(cvdTranslation)
    return result

def shape (tok):
    # assert(type(tok) == str or type(tok) == unicode)
    # assert(shapeTranslation is not None)
    # assert(type(shapeTranslation) == str)
    # print "type",type(shapeTranslation)
    result = tok.translate(shapeTranslation)
    return result;


def makeCVDTranslation ():
    """Makes a character translation for the CVD feature"""
    source = ""
    target = ""
    source += "aeiou"
    target += "v" * 5
    source += "AEIOU"
    target += "V" * 5
    source += "bcdfghjklmnpqrstvwxyz"
    target += "c" * 21
    source += "BCDFGHJKLMNPQRSTVWXYZ"
    target += "C" * 21
    source += "0123456789"
    target += "D" * 10
    # return string.maketrans(source,target)
    charMap = dict()
    for i in range(0,len(source)):
        s = ord(source[i])
        t = ord(target[i])
        charMap[s] = t
    return charMap
    
def makeShapeTranslation ():
    """Makes a character translation for the 'shape' feature, which maps upper/lowercase letters to X/x and digits to 'd'."""
    source = ""
    target = ""
    source += "aeiou"
    source += "bcdfghjklmnpqrstvwxyz"
    target += "x" * 26
    source += "AEIOU"
    source += "BCDFGHJKLMNPQRSTVWXYZ"
    target += "X" * 26
    source += "0123456789"
    target += "d" * 10
    # return string.maketrans(source,target)
    charMap = dict()
    for i in range(0,len(source)):
        s = ord(source[i])
        t = ord(target[i])
        charMap[s] = t
    return charMap
    
    

def hasNonInitialPeriod (tok):
    """Examples: St., I.B.M. """         
    # Clojure original: 
    #   #(some? (re-matches #"(\p{L}+\.)+(\p{L}+)?" %)
    if (re.search('^([A-Za-z]+\.)+([A-Za-z]+)?$',tok)):
        return True
    else:
        return False

def hasNoVowels (tok):
    """Returns true if there are no vowels in the argument token."""
    for c in tok:
        if (c in VOWELS):
            return False
    return True

def isAllCapitalized (tok):
    "Returns true if token consists solely of capital letters"
    for sub in tok:
        if (not sub.isalpha() or sub.islower()):
            return False
    return True

def hasCapLettersOnly (tok):
    """Returns true if token has at least one capital letter, and no lower case letters.  
       Can also contain digits, hypens, etc."""
    hasCap = False
    for sub in tok:
        if (sub.isalpha()):
            if (sub.islower()):
                return False
            else:
                hasCap = True
    return hasCap

def hasMixedChars (tok):
    hasLetters = False
    hasDigits  = False
    hasOther  = False
    for c in tok:
        if (c.isalpha()):
            hasLetters = True
        elif (c.isdigit()):
            hasDigits = True
        else:
            hasOther = True
    count = 0
    if (hasLetters):
        count += 1
    if (hasDigits):
        count += 1
    if (hasOther):
        count += 1
    return (count > 1)


def hasInternalPunctuation (tok):
    "A word with an internal apostrophe or ampersand.  Example: O'Connor"
    if (re.search('^[A-Za-z]+[\'&][A-Za-z]+$',tok)):
        return True
    else:
        return False
    
def hasInternalHyphen (tok):
    if (re.search('^[A-Za-z]+(-[A-Za-z]+)+$',tok)):
        return True
    else:
        return False

def isAllNonLetters (tok):
    "Returns true if the token consists only of non-alphabetic characters" 
    for sub in tok:
        if (sub.isalpha()):
            return False
    return True

def isMixedCase (tok):
    """Returns true if the token contains at least one upper-case letter and another character type,
       which may be either a lower-case letter or a non-letter.  Examples: ProSys, eBay """
    # Clojure original:
    #     (fn [token]    ;; ProSys, eBay
    #        (if-not (empty? token)
    #              (->> (map #(Character/isUpperCase %) token)
    #                   distinct
    #                   count
    #                   (= 2))
    #              false))
    hasUpper = False
    hasLower = False
    for c in tok:
        if (c.isupper()):
            hasUpper = True
        else:
            hasLower = True
    return hasUpper and hasLower

def nonAlphaChars (tok):
    """Returns a version of the token where alphabetic characters have been removed, 
       and digits have been replaced by 'D'. This may be the empty string of course. """
    result = ""
    for sub in tok:
        if (sub.isdigit()):
            result += "D"
        elif (not sub.isalpha()):
            result += sub
    return result

def compressedCVD (tok):
    compressed = ""
    cvdVal = cvd(tok)
    prev = ""
    for i in range(0,(len(cvdVal))):
        symbol = cvdVal[i].upper()
        if (symbol != prev):
            compressed += symbol
        prev = symbol
    return compressed


def isWordWithDigit (tok):
    "Examples: W3C, 3M"
    if (re.search('^[A-Za-z\d]*([A-Za-z]\d|\d[A-Za-z])[A-Za-z\d]*$',tok)):
        return True
    else:
        return False


def getFeatVal (featFun, token):
    """Applies a feature function to the token, converting None or empty string values to EMPTY, and 
       True or False values to strings 'true' or 'false', resp."""
    value = apply(featFun,[token])
    if (value == None or value == ""):
        return EMPTY
    elif (value == True):
        return "true"
    elif (value == False):
        return "false"
    else:
        return value    

def nonOverlapping (files1, files2):
    """Takes two lists of files; raises an exception if they overlap."""
    for file1 in files1:
        for file2 in files2:
            if (file1 != None and file2 != None and file1 == file2):
                raise RuntimeError(format("Can't overwrite %s" % file1)) 

def hasXorZ (tok):
    return ("X" in tok or "Z" in tok)
            
def join (lst,sep=" "):
    """Takes a list of objects of arbitrary type, plus an optional separator string.  Returns a string in which the 'str' 
     representations of the objects are joined by the separator, whose default value is just a single space."""
    strg = ""
    for i,x in enumerate(lst):
        if (i > 0):
            strg += sep
        strg += str(x)
    return strg

 
def split (strg,sep=" "):
    tokens = []
    for tok in strg.split(sep):
        if (tok != ""):
            tokens.append(tok)
    return tokens
      

def containsSlash (tok):
    "Returns true if the token contains a '/'."
    for c in tok:
        if (c == '/'):
            return True
    return False

def uniqueChars (tok):
    """Takes a token; returns the set of unique characters within it."""
    charSet = set()
    charList = []
    for c in tok:
        if (c not in charSet):
            charSet.add(c)
            charList.append(c)
    return join(charList,"")

def sortChars (tok):
    """Takes a token; returns a reordered version of it which has been sorted by character."""
    chars = []
    for c in tok:
        chars.append(c)
    chars.sort()
    return join(chars,"")

def stripVowels (tok):
    "Returns a version of the token from which all vowels have been removed. "
    nonVowels = []
    for c in tok:
        if (c not in VOWELS):
            nonVowels.append(c)
    result = join(nonVowels,"")
    if (result == ""):
        result = EMPTY
    return result
   
    
def defineBuiltInFeatures ():    

    """Defines the built-in features for this package"""    
    
    defFeat('token', lambda(x) : x)
    
    defFeat('shape', shape)
    defFeat('has-cap-letters-only', hasCapLettersOnly)
    defFeat('mixed-chars', hasMixedChars)
    defFeat('word-with-digit', isWordWithDigit)
    defFeat('upper-token', lambda (x) : x.upper())
    defFeat('mixed-case', isMixedCase)
   
    defFeat('non-initial-period', hasNonInitialPeriod)
    defFeat('internal-hyphen', hasInternalHyphen)
    defFeat('all-digits', lambda (x) : x.isdigit())

    defFeat('has-no-vowels', hasNoVowels)
    
    defFeat('all-capitalized', isAllCapitalized)
    defFeat('all-non-letters', isAllNonLetters)
    defFeat('initial-capitalized', lambda (x) : x[0].isupper())
    defFeat('internal-punctuation', hasInternalPunctuation)
    defFeat('non-alpha-chars', nonAlphaChars)
    
    defFeat('prefix3', lambda (x) : prefix(x,3))
    defFeat('prefix4', lambda (x) : prefix(x,4))
    
    defFeat('suffix4', lambda (x) : suffix(x,4))
    defFeat('suffix2', lambda (x) : suffix(x,2))
    defFeat('suffix3', lambda (x) : suffix(x,3))
    defFeat('suffix1', lambda (x) : suffix(x,1))

    defFeat('cvd', cvd)
    defFeat('compressed-cvd', compressedCVD)
    
    defFeat('ends-with-digit', lambda (x) : (not x[0].isdigit()) and x[-1].isdigit())
    defFeat('has-X-or-Z', hasXorZ)
    defFeat('contains-slash', containsSlash)
    
    defFeat('constant', lambda (x) : "CONST")
    defFeat('unique-chars', uniqueChars)
    defFeat('strip-vowels', stripVowels)

class FeatListEntry(object):
    """Comprises a U (unigram) or B (bigram) type indicator, a window, and a list of FeatRefs."""
    def __init__ (self):
        self.type      = "U"
        self.featRefs  = []
        self.positions = None
        self.bow       = False
   
class FeatRef(object):
    """Represents a reference to a feature in the feature list file.  Is just the feature name and its relative position."""    
    def __init__ (self,feat,pos=0):
        self.feat = feat
        self.pos  = pos

class FeatDefinition(object):
    """Represents the information needed to extract the feature"""
    def __init__ (self,name):
        self.name         = name  # The string name.
        self.tokenFunc    = None  # Definitions have these unless they are are sequence-oriented.
        self.sequenceFunc = None  # Every definition will have one, constructed from tokenFunc if an explicit one is not given.
        self.isSequence   = False # A sequential feature will have only a sequenceFunc

# Call the 'main' function if we are being invoke in a script context. 
if (__name__ == "__main__"):
    main()
