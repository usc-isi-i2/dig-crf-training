# Codes for HTTP response. 

SUCCESS_CODE=200
FAILURE_CODE=400

# Make a unique output directory for this invocation

OUTDIR=$(mktemp -d -p outputs)

# The intermediate files in OUTDIR

TRAIN_JSON="$OUTDIR/training.json"
TRAIN_LABELS="$OUTDIR/training.labeled"
TRAIN_FEATS=$OUTDIR/training.feats
LOG_FILE="$OUTDIR/log.txt"

# The result file in OUTDIR

MODEL=$OUTDIR/training.model

# The input files which are constant for all invocations.

FEAT_LIST="features.hair-eye"
TEMPLATES=dig-hair-eye-train.templates

# Flag arguments to the different components.  

LABEL_FLAGS=""
FEAT_FLAGS="--labeled --featlist $FEAT_LIST"
TRAIN_FLAGS="-f 1 -a CRF-L2"


# Write the contents of stdin to TRAIN_JSON.  This is kind of silly... 

python -u stdin_to_file.py $TRAIN_JSON &>>$LOG_FILE

# Convert the JSON to name annotations

python -u json_to_name_annotations.py --inputs $TRAIN_JSON --output $TRAIN_LABELS $LABEL_FLAGS &>>$LOG_FILE

# Featurize the name annotations

python -u crf_features.py --input $TRAIN_LABELS --output $TRAIN_FEATS $FEAT_FLAGS &>>$LOG_FILE

# Train the model on the features

crf_learn $TRAIN_FLAGS $TEMPLATES $TRAIN_FEATS $MODEL &>>$LOG_FILE

# Output the model on stdout

cat $MODEL 2>>$LOG_FILE

# If the model file exists, we have succeeded. Emit 200 on stderr.
if [ -e $MODEL ]
then
    echo "SUCCESS" &>>$LOG_FILE
    >&2 echo $SUCCESS_CODE 
# Otherwise, we have failed. Output failure code on stderr
else
    echo "FAILURE" &>>$LOG_FILE
    >&2 echo $FAILURE_CODE
fi






