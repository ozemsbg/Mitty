Read model format
=================

Illumina model
--------------

```
{
  'model_class': 'illumina',       # This tells Mitty which model class to use
  'model_description': 'My model', # This will be printed in the one page figure describing the model. Good for record keeping
  'bq_mat': None,                  # numpy.array with shape (2, L, 94) storing BQ distribution
  'cum_bq_mat': None,              # numpy.array with shape (2, L, 94) storing normalized cumulative BQ distribution
  'tlen': None,                    # numpy.array with shape (tmax,) giving distribution of template lengthts
  'cum_tlen': None,                # numpy.array with shape (tmax,) storing normalized cumulative distribution of template lengthts
  'mean_rlen': L,                  # These are all L, the length of the read 
  'max_rlen': L, 
  'min_rlen': L, 
}
```
Where:
 
 L = length of the read 
 tmax = the maximum template length we allow

To gain an intuition of what these parameters mean please see the read model description
figures, study the synthetic model generator code (`mitty/simulation/sequencing/syntheticsequencer.py`) 
and the Illumina read model code (`mitty/simulation/illumina.py`).