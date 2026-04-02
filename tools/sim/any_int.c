/*	This file is part of the module ANY_INT.
	Written by Dick Grune, dick@dickgrune.com
	$Id: any_int.c,v 1.8 2023-05-17 15:42:49 dick Exp $
*/

#include	<stdio.h>

#include	"any_int.h"

#define	MAX_ANY_UINT_DIGITS	40	/* good for 128 bits, including sign */

/* Library module source prelude */
#undef	_ANY_UINT_CODE_
#ifndef	lint
#define	_ANY_UINT_CODE_
#endif
#ifdef	LIB
#define	_ANY_UINT_CODE_
#endif

#ifdef	_ANY_UINT_CODE_

/* Library module source code */

static const char * /* transient */
int2string(vlong_uint val, int neg) {
	static char buff[MAX_ANY_UINT_DIGITS];
	char *res = &buff[MAX_ANY_UINT_DIGITS-1];	/* end of buffer */
	*res = '\0';					/* insert EOS */

	do {	/* one decimal character, the first always */
		*--res = "0123456789ABCDEF"[val % 10];
		val = val / 10;
	} while (val > 0);

	if (neg) {
		*--res = '-';
	}

	return res;
}

const char *	/* transient */
any_int2string(vlong_int val) {
	int neg = 0;
	if (val < 0) {
		val = - val;
		neg = 1;
	}
	return int2string((vlong_uint)val, neg);
}

const char *	/* transient */
any_uint2string(vlong_uint val) {
	return int2string(val, 0);
}

#define	is_safe_to_add(a, b)		((a) <= VLONG_INT_MAX - (b))
#define	is_safe_to_multiply(a, b)	((a) <= VLONG_INT_MAX / (b))

const char *	/* transient */
any_mem_size2string(vlong_uint val) {
	static char buff[8];
	char *res = buff;

	if (val <= 999) {
		/* 'val' fits in " 999  ", which is a differnt format */
		/* no rounding needed */
		sprintf(res, " %3d  ", val);
		return res;
	}

	const char *marker;		/* decimal, 1k0 = 1000 */
	vlong_int unit;			/* 1/1000 * value of marker */
	for (	marker = "kMGTPE", unit = 1;
		*marker && is_safe_to_multiply(unit, 1000);
		marker++, unit *= 1000
	) {	/* from loop entrance or continuation: 999.950*unit <= 'val' */
		if (	!is_safe_to_multiply(999950, unit)
		||	val <= 999950*unit - 1
		) {	/* 999.950*unit <= 'val' <= 999950*unit - 1 */
			/* that is, 'val' fits in " 999?9" (after rounding) */
			break;
		}
		/* !('val' <= 999950*unit - 1) ==
		   ('val' > 999950*unit - 1) ==
		   ('val' >= 999950*unit) ==
		   (999950*unit <= 'val')
		*/
	}
	/* from loop exit: 999.950*unit <= 'val' <= 999950*unit - 1 */
	/* round it upwards, avoiding overflow */
	if (	is_safe_to_multiply(50, unit)
	&&	is_safe_to_add(val, 50*unit)
	) {	/* 999.950*unit <= 'val' <= 999950*unit - 1 */
		val += (50*unit);
		/* 1049.950*unit <= 'val <= 1000000*unit - 1 */
	}
	/* truncate, in two steps */
	val /= unit;
	/* 1049 <= 'val <= 999999 */
	val /= 100;
	/* 10 <= 'val <= 9999 */
	/* and convert type */
	int mm = val;
	sprintf(res, " %3d%c%1d", mm / 10, *marker, mm % 10);
	return res;
}

/* End library module source code */
#endif	/* _ANY_UINT_CODE_ */

#ifdef	lint
static void
satisfy_lint(void *x) {
	(void)any_int2string(0);
	(void)any_uint2string(0);
	(void)any_mem_size2string(0);
	satisfy_lint(x);
}
#endif	/* lint */
