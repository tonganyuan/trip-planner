import type { FamilyInfo, FamilyMutationResponse } from '@/types'
import apiClient from './http'
import { extractError } from './auth'

/** 获取家庭信息（含成员列表） */
export async function fetchFamily(): Promise<FamilyInfo> {
  try {
    const response = await apiClient.get<FamilyInfo>('/api/family')
    return response.data
  } catch (error: any) {
    throw new Error(extractError(error, '获取家庭信息失败'))
  }
}

/** 添加家庭成员（创建全新账号并共享数据） */
export async function addFamilyMember(
  username: string,
  password: string,
  displayName = ''
): Promise<FamilyMutationResponse> {
  try {
    const response = await apiClient.post<FamilyMutationResponse>('/api/family/members', {
      username,
      password,
      display_name: displayName
    })
    return response.data
  } catch (error: any) {
    throw new Error(extractError(error, '添加成员失败'))
  }
}

/** 移除家庭成员（仅户主） */
export async function removeFamilyMember(memberId: number): Promise<FamilyMutationResponse> {
  try {
    const response = await apiClient.delete<FamilyMutationResponse>(`/api/family/members/${memberId}`)
    return response.data
  } catch (error: any) {
    throw new Error(extractError(error, '移除成员失败'))
  }
}

/** 修改家庭名称（仅户主） */
export async function renameFamily(name: string): Promise<FamilyMutationResponse> {
  try {
    const response = await apiClient.patch<FamilyMutationResponse>('/api/family', { name })
    return response.data
  } catch (error: any) {
    throw new Error(extractError(error, '修改家庭名称失败'))
  }
}
