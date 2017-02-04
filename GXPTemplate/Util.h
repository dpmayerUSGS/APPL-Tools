//----------------------------------------------------------------------------
// 
//                                UNCLASSIFIED
// 
//                     Copyright © 1989-2013 BAE Systems
//                            ALL RIGHTS RESERVED
// Use of this software product is governed by the terms of a license
// agreement. The license agreement is found in the installation directory.
//  
// The export of the information contained within this document is governed
// by the Export Administration Regulations (EAR) of the United States. This
// document may not be transferred to a non-U.S. person/entity without the
// proper prior authorization of the U.S. Government. Violations may result
// in administrative, civil or criminal penalties.
//  
//               For support, please visit http://www.baesystems.com/gxp
//----------------------------------------------------------------------------

#ifndef __UTIL_H__
#define __UTIL_H__

//-------------------------------------------------
// Util
class Util
{
public:

   static bool
   checkStatus(
      GSIT_STATUS comm_status,
      const GXP_API::ApiStatus& gxp_status);
};

#endif // __UTIL_H__
