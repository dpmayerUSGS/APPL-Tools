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

#ifndef __OSUTIL_H__
#define __OSUTIL_H__

//-------------------------------------------------
// typedefs
typedef int pid_t;

//-------------------------------------------------
// OsUtil
class OsUtil
{
public:

   static pid_t
   StartApplication(
      const char* application);

   static pid_t
   StartGxpApplication();

   static std::string
   NormalizeLocalPath(
     const char* filename); 

   static void
   WaitOnProcess(
      pid_t pid);

   static void
   Sleep(
      int seconds);
};

#endif // __OSUTIL_H__

